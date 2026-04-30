import re
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, ToolException, tool
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from langfuse import Langfuse, get_client, propagate_attributes
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler

from agent.prompt import SYSTEM_PROMPT
from config import get_langfuse_settings, get_llm_settings, get_logger
from vector_db import VectorDatabase


def _build_chat_llm() -> ChatOpenAI | AzureChatOpenAI:
    """Build a ChatOpenAI client pointed at OPENAI_ENDPOINT."""
    settings = get_llm_settings()
    extra_kwargs: dict[str, Any] = {}
    if settings.reasoning_effort:
        extra_kwargs["reasoning_effort"] = settings.reasoning_effort

    compat_base = settings.openai_base_url.strip()
    if compat_base:
        return ChatOpenAI(
            model=settings.deployment_name,
            api_key=settings.api_key,
            base_url=compat_base.rstrip("/"),
            default_headers={"api-key": settings.api_key},
            streaming=True,
            temperature=settings.temperature,
            **extra_kwargs,
        )
    return AzureChatOpenAI(
        azure_deployment=settings.deployment_name,
        api_key=settings.api_key,
        azure_endpoint=settings.endpoint.rstrip("/"),
        api_version=settings.api_version,
        default_headers={"api-key": settings.api_key},
        streaming=True,
        temperature=settings.temperature,
        **extra_kwargs,
    )


logger = get_logger("agent.service")

# Maximum number of tool-calling iterations to prevent infinite loops
MAX_TOOL_ITERATIONS = 10

# Sentinel marker the LLM uses to recognize that the product catalog is
# unreachable (DB not connected, HTTP error, etc.). The system prompt
# instructs the LLM how to respond when it sees this marker so the model
# does not silently fall back to inventing products from prior knowledge.
CATALOG_UNAVAILABLE_MARKER = "[CATALOG_UNAVAILABLE]"
CATALOG_UNAVAILABLE_TOOL_MESSAGE = (
    f"{CATALOG_UNAVAILABLE_MARKER} The product catalog service is currently "
    "unreachable. Do NOT invent or recall products from prior knowledge. "
    "Tell the user the catalog is temporarily unavailable and ask them to "
    "try again shortly."
)

# Langfuse initialization state
_langfuse_initialized = False


def _init_langfuse() -> bool:
    """
    Initialize Langfuse client if enabled and configured.

    Uses the singleton pattern - Langfuse client is initialized once at startup.

    Returns:
        True if Langfuse was successfully initialized, False otherwise
    """
    global _langfuse_initialized  # noqa: PLW0603
    if _langfuse_initialized:
        return True

    settings = get_langfuse_settings()
    if settings.enabled and settings.public_key and settings.secret_key:
        try:
            Langfuse(
                public_key=settings.public_key,
                secret_key=settings.secret_key,
                host=settings.host,
            )
            _langfuse_initialized = True
            logger.info("Langfuse tracing initialized successfully")
        except Exception:
            logger.exception("Failed to initialize Langfuse")
            return False
    else:
        logger.info("Langfuse tracing disabled or not configured")
    return _langfuse_initialized


def _get_langfuse_handler() -> LangfuseCallbackHandler | None:
    """
    Get a Langfuse callback handler for tracing if available.

    Returns a new handler instance only when Langfuse has been successfully
    initialized; otherwise returns None.

    Note: In Langfuse v3, session_id and user_id are passed via config metadata,
    not through the CallbackHandler constructor.

    Returns:
        LangfuseCallbackHandler instance if Langfuse is initialized, None otherwise
    """
    if not _langfuse_initialized:
        return None

    return LangfuseCallbackHandler()


def _convert_history_to_messages(history: list[dict[str, str]]) -> list[BaseMessage]:
    """Convert history dicts to LangChain message objects."""
    messages: list[BaseMessage] = []
    for msg in history:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    return messages


async def _execute_tool(
    tool_name: str, tool_args: dict[str, Any], tool_registry: dict[str, BaseTool]
) -> tuple[str, bool]:
    """
    Execute a tool and return the result with success status.

    Args:
        tool_name: Name of the tool to execute
        tool_args: Arguments to pass to the tool
        tool_registry: Registry mapping tool names to tool instances

    Returns:
        Tuple of (result_string, success_bool)
    """
    if tool_name not in tool_registry:
        return f"Unknown tool: {tool_name}", False

    tool_func = tool_registry[tool_name]
    try:
        result = await tool_func.ainvoke(tool_args)
        return str(result), True
    except (ToolException, ValueError, TypeError, KeyError) as e:
        logger.exception("Tool execution failed: %s", tool_name)
        return f"Error executing tool: {e}", False


class Agent:
    """
    Agent service for handling LLM interactions with streaming support.

    Uses Azure OpenAI with LangChain for chat completions and tool calling.
    Supports agentic tool-calling loop with user notifications.
    """

    def __init__(
        self,
        vector_database: VectorDatabase | None = None,
    ) -> None:
        """
        Initialize the agent with Azure OpenAI configuration.

        Args:
            vector_database: VectorDatabase for RAG search (calls sqlite-vec service)
        """
        # Initialize Langfuse tracing (singleton)
        _init_langfuse()

        llm = _build_chat_llm()

        # Always register search_products. When the database is unavailable
        # the tool returns an explicit error sentinel instead of being
        # removed entirely — otherwise the LLM tends to hallucinate the tool
        # call as plain text and invent products from prior knowledge
        # (see CATALOG_UNAVAILABLE_TOOL_MESSAGE / system prompt scenario D).
        self.tools: list[BaseTool] = [Agent._create_rag_tool(vector_database)]
        if vector_database is not None:
            logger.info("Agent initialized with RAG tool")
        else:
            logger.warning(
                "Agent initialized with RAG tool stub (vector database "
                "unavailable — search_products will return an error)"
            )

        self.llm = llm.bind_tools(self.tools)
        self.tool_registry: dict[str, BaseTool] = {
            tool.name: tool for tool in self.tools
        }

    @staticmethod
    def _create_rag_tool(db: VectorDatabase | None) -> BaseTool:
        """
        Create the RAG search tool bound to the given vector database.

        The tool is registered unconditionally so the LLM has a consistent
        function-calling surface. When ``db`` is ``None`` (database not
        configured / not reachable at connection time) or when a runtime call
        fails (HTTP error, timeout, etc.), the tool returns
        :data:`CATALOG_UNAVAILABLE_TOOL_MESSAGE`. The system prompt teaches
        the model how to surface this to the user without hallucinating.

        Args:
            db: The VectorDatabase instance, or ``None`` when unavailable.

        Returns:
            LangChain tool for semantic search.
        """

        @tool
        async def search_products(query: str) -> str:
            """
            Search for fashion products in the catalog using semantic search (RAG).

            Use this tool when the customer asks about clothing items, products,
            or wants to browse/shop. This searches our inventory using AI-powered
            semantic understanding via sqlite-vec and returns relevant products.

            Args:
                query: The search query describing the products the customer wants
                      (e.g., "red jeans", "winter jackets", "cozy sweater")

            Returns:
                Formatted product information including prices, colors, sizes, and details.
                If no products found, returns a message indicating no matches.
                If the catalog service is unreachable, returns the
                CATALOG_UNAVAILABLE sentinel so the LLM can surface a proper
                error message rather than inventing products.
            """
            if db is None:
                logger.warning(
                    "search_products invoked but no vector database is "
                    "available — returning CATALOG_UNAVAILABLE sentinel"
                )
                return CATALOG_UNAVAILABLE_TOOL_MESSAGE

            try:
                search_query = Agent._extract_product_query(query)
                logger.info("RAG searching: '%s' (from: '%s')", search_query, query)

                products = await db.search(query=search_query, limit=10)
            except Exception:
                logger.exception("RAG search failed — catalog service unreachable")
                return CATALOG_UNAVAILABLE_TOOL_MESSAGE

            if not products:
                logger.info("No products found for query")
                return "No products found matching that description in our current catalog."

            logger.info("RAG retrieved %d products", len(products))
            return str(db.format_products(products))

        return search_products

    @staticmethod
    def _extract_product_query(message: str) -> str:
        """
        Extract product type from query, removing price constraints and question words.
        This method is needed to extract user intent. We could do it with LLM, but it's faster to do it here.

        Examples:
            "gloves under 50$" -> "gloves"
            "blue jeans less than 100" -> "blue jeans"
            "show me affordable shirts" -> "shirts"

        Args:
            message: Original user message

        Returns:
            Simplified query focusing on product type
        """
        query = message.lower()
        # Remove price patterns with keywords
        query = re.sub(
            r"\b(under|less than|below|cheaper than|more than|above)\s*\$?\d+\s*(dollars?|usd|\$)?",
            "",
            query,
        )
        # Remove standalone price values
        query = re.sub(r"\$\d+", "", query)
        # Remove affordability words
        query = re.sub(r"\baffordable\b|\bcheap\b|\bexpensive\b|\bbudget\b", "", query)
        # Remove question/request phrases and filler words
        query = re.sub(
            r"\b(do you have|show me|looking for|i need|i want|what about|i'm|please|any)\b",
            "",
            query,
        )
        # Remove punctuation
        query = re.sub(r"[?!.,;:]", "", query)
        # Normalize whitespace
        query = " ".join(query.split())

        return query.strip() or message

    @staticmethod
    def _build_messages_from_transcript(
        transcript: list[dict[str, str]],
    ) -> list[BaseMessage]:
        """Build LangChain messages: system prompt + full conversation transcript."""
        messages: list[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT.strip())]
        messages.extend(_convert_history_to_messages(transcript))
        return messages

    @staticmethod
    def _build_config() -> RunnableConfig:
        """Build the LLM config with Langfuse callback if available."""
        config: RunnableConfig = {}
        langfuse_handler = _get_langfuse_handler()
        if langfuse_handler:
            config["callbacks"] = [langfuse_handler]
        return config

    async def _process_tool_calls(
        self, full_response: AIMessageChunk, messages: list[BaseMessage]
    ) -> None:
        """Execute tool calls and append results to messages."""
        logger.info("Processing %d tool call(s)", len(full_response.tool_calls))
        messages.append(full_response)

        for tool_call in full_response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_call_id = tool_call["id"]

            result, _ = await _execute_tool(tool_name, tool_args, self.tool_registry)
            messages.append(ToolMessage(content=result, tool_call_id=tool_call_id))

    async def astream(
        self,
        messages: list[dict[str, str]],
        *,
        session_id: str | None = None,
        visitor_id: str | None = None,
    ) -> AsyncIterator[str]:
        """
        Stream agent responses asynchronously with conversation context.

        Implements a full agentic loop that:
        1. Streams LLM response tokens
        2. Detects and executes tool calls
        3. Notifies user about tool execution
        4. Continues until LLM provides final answer

        Args:
            messages: Full conversation for this turn: ``role`` / ``content`` dicts
                (typically ends with the current user message).
            session_id: Optional session ID for Langfuse tracing
            visitor_id: Optional visitor ID for Langfuse tracing

        Yields:
            Response chunks as strings (including tool call notifications)
        """
        lc_messages = Agent._build_messages_from_transcript(messages)
        config = Agent._build_config()

        # Propagate session_id and user_id to all Langfuse traces (when provided)
        with propagate_attributes(session_id=session_id, user_id=visitor_id):
            async for chunk in self._run_agentic_loop(lc_messages, config):
                yield chunk

            # Flush Langfuse events at the end of the request
            if _langfuse_initialized:
                try:
                    get_client().flush()
                except Exception:
                    logger.exception("Failed to flush Langfuse events")

    async def _run_agentic_loop(
        self, messages: list[BaseMessage], config: RunnableConfig
    ) -> AsyncIterator[str]:
        """Run the agentic loop until no more tool calls or max iterations."""
        for iteration in range(MAX_TOOL_ITERATIONS):
            full_response: AIMessageChunk | None = None

            async for chunk in self.llm.astream(messages, config=config):
                chunk_msg = chunk if isinstance(chunk, AIMessageChunk) else None
                if chunk_msg:
                    full_response = (
                        chunk_msg
                        if full_response is None
                        else full_response + chunk_msg
                    )

                content: Any = getattr(chunk, "content", "")
                if content:
                    yield str(content)

            if full_response is None or not full_response.tool_calls:
                logger.info("Agentic loop completed after %d iterations", iteration + 1)
                return

            await self._process_tool_calls(full_response, messages)
        logger.warning("Reached maximum tool iterations (%d)", MAX_TOOL_ITERATIONS)
        yield "\n\n⚠️ Reached maximum tool call limit. Please rephrase your question."
