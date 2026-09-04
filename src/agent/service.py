import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.messages.ai import UsageMetadata
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.tools import BaseTool, tool
from langchain_litellm import ChatLiteLLM
from langfuse.langchain import CallbackHandler

from agent.prompt import load_fallback_prompt
from config import (
    get_llm_settings,
    get_logger,
    resolve_default_model,
)
from document_rag.repository import DocumentRagRepository
from mcp_integration import open_mcp_tools
from tracing import (
    flush_langfuse_async,
    get_client,
    get_prompt_text,
    init_langfuse,
    is_langfuse_initialized,
    propagate_attributes,
)
from vector_db import VectorDatabase


def _build_llm_kwargs(settings: Any) -> dict[str, Any]:
    """Assemble the shared LiteLLM connection kwargs from LLM settings.

    The shared ``LLM_API_KEY`` is forwarded only for an explicit single-model
    deployment (``LLM_MODEL`` set). With no ``LLM_MODEL`` the app runs in
    multi-provider picker mode, where forwarding one key to whichever provider a
    picked model routes to would leak it; instead LiteLLM resolves each
    provider's own credential from its standard env var (OPENAI_API_KEY,
    ANTHROPIC_API_KEY, …).
    """
    kwargs: dict[str, Any] = {}
    api_base = settings.api_base.strip()
    if api_base:
        kwargs["api_base"] = api_base.rstrip("/")
    if settings.api_key and settings.model:
        kwargs["api_key"] = settings.api_key
        # Gateways such as Azure APIM authenticate via the `api-key` header.
        kwargs["extra_headers"] = {"api-key": settings.api_key}
    if settings.api_version:
        kwargs["api_version"] = settings.api_version
    if settings.reasoning_effort:
        kwargs["reasoning_effort"] = settings.reasoning_effort
    return kwargs


def _build_chat_llm(model: str | None = None) -> BaseChatModel:
    """Build a LiteLLM chat client for the configured model.

    ``stream_options`` is set explicitly because ``langchain_litellm`` only
    defaults it on for OpenAI-ish models, and LiteLLM's stream wrapper drops the
    usage chunk entirely unless ``include_usage`` is requested. Without it a
    streamed Anthropic turn reports no token counts at all. LiteLLM whitelists
    ``stream_options`` from its unsupported-parameter check, so passing it is
    safe for every provider.
    """
    settings = get_llm_settings()
    return ChatLiteLLM(
        model=model or settings.model,
        streaming=True,
        temperature=settings.temperature,
        stream_options={"include_usage": True},
        **_build_llm_kwargs(settings),
    )


logger = get_logger("agent.service")

# Maximum number of tool-calling iterations to prevent infinite loops
MAX_TOOL_ITERATIONS = 10

# Name of the chat system prompt as registered in Langfuse prompt management.
# When the fetch fails (Langfuse disabled, unreachable, or the prompt is missing)
# the agent falls back to ``agent.prompt.SYSTEM_PROMPT``.
CHAT_SYSTEM_PROMPT_NAME = "CHAT_SYSTEM_PROMPT"

# Per-task source accumulator for the document RAG tool. Each asyncio Task
# (i.e. each astream() call) gets its own list, so concurrent streams never
# interfere with each other.
_current_sources: ContextVar[list[dict[str, Any]]] = ContextVar("_current_sources")


_IMAGE_MIME_TYPES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})


# LiteLLM routes other than `anthropic/` that can serve Claude in Anthropic's
# native request format, where `cache_control` on system content is understood.
# Both also serve non-Anthropic models, so the model id must still name Claude.
_ANTHROPIC_ROUTE_PREFIXES = ("bedrock/", "bedrock_converse/", "vertex_ai/")


def _is_anthropic_model(model: str | None) -> bool:
    """Return True when *model* routes to Anthropic through LiteLLM.

    Matches the direct ``anthropic/…`` route as well as the Claude models served
    via Bedrock and Vertex (``bedrock/anthropic.claude-…``, ``vertex_ai/claude-…``).

    Matched on the route prefix, not on ``"claude"`` appearing anywhere: model
    ids are LiteLLM ``provider/model`` pairs whose model half can be an operator
    -chosen alias (``azure/<deployment>``), so a bare substring test would send
    Anthropic-only content to a provider that rejects it.
    """
    if not model:
        return False
    normalized = model.lower()
    if normalized.startswith("anthropic/"):
        return True
    return normalized.startswith(_ANTHROPIC_ROUTE_PREFIXES) and "claude" in normalized


def _apply_prompt_cache(
    messages: list[BaseMessage], model: str | None
) -> list[BaseMessage]:
    """Mark the system prompt as an Anthropic prompt-cache breakpoint.

    Anthropic builds its cache prefix in the order ``tools → system → messages``,
    so a single ``cache_control`` breakpoint on the system message covers both
    the persona prompt and every bound tool definition — together the largest
    stable block of the request, re-sent on all ~2 LLM calls of every turn.

    No-op for non-Anthropic models: ``cache_control`` is Anthropic-specific and
    the multi-model picker can route a turn to OpenAI or Azure.
    """
    if not messages or not _is_anthropic_model(model):
        return messages
    head = messages[0]
    # Only a plain string system prompt is converted. Anything else is already
    # structured content this function did not build and must not reshape.
    if not isinstance(head, SystemMessage) or not isinstance(head.content, str):
        return messages

    cached_system = SystemMessage(
        content=[
            {
                "type": "text",
                "text": head.content,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    )
    return [cached_system, *messages[1:]]


def _build_trace_input(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build a compact Langfuse trace input from the turn transcript.

    Strips base64 attachment payloads so the trace input stays small and
    readable, keeping only attachment names and MIME types for context.
    """
    cleaned: list[dict[str, Any]] = []
    for msg in messages:
        entry: dict[str, Any] = {
            "role": msg.get("role"),
            "content": msg.get("content", ""),
        }
        attachments = msg.get("attachments")
        if attachments:
            entry["attachments"] = [
                {"name": a.get("name"), "mime_type": a.get("mime_type")}
                for a in attachments
            ]
        cleaned.append(entry)
    return cleaned


def _convert_history_to_messages(history: list[dict[str, Any]]) -> list[BaseMessage]:
    """Convert history dicts to LangChain message objects.

    When a user message carries ``attachments`` with image MIME types the
    message is built as a multimodal ``HumanMessage`` with interleaved text
    and ``image_url`` content blocks so the LLM can see the images natively.
    """
    messages: list[BaseMessage] = []
    for msg in history:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user":
            attachments: list[dict[str, Any]] = msg.get("attachments") or []
            image_parts = [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{a['mime_type']};base64,{a['data']}",
                    },
                }
                for a in attachments
                if a.get("mime_type") in _IMAGE_MIME_TYPES
            ]
            if image_parts:
                parts: list[str | dict[Any, Any]] = [
                    {"type": "text", "text": content},
                    *image_parts,
                ]
                messages.append(HumanMessage(content=parts))
            else:
                messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    return messages


def _merge_call_usage(
    current: dict[str, int] | None, usage_metadata: UsageMetadata | None
) -> dict[str, int] | None:
    """Fold one chunk's ``usage_metadata`` into the running total for ONE LLM call.

    Uses a field-wise max rather than a sum because LiteLLM reports usage more
    than once per Anthropic call — ``message_start`` carries the input and cache
    counts, ``message_delta`` carries the output count. Each report is a
    cumulative snapshot of that call, not a delta, so summing them would
    double-count the input tokens. Providers that report usage exactly once
    (OpenAI) are unaffected: max of a single value is that value.

    Note ``prompt_tokens`` is *inclusive* of the two cache counts: LiteLLM adds
    ``cache_creation_input_tokens`` and ``cache_read_input_tokens`` into
    ``prompt_tokens`` for Anthropic. They are sub-totals of it, never additions
    to it — see ``_partition_input_tokens``.
    """
    if not usage_metadata:
        return current
    details = usage_metadata.get("input_token_details") or {}
    incoming = {
        "prompt_tokens": int(usage_metadata.get("input_tokens") or 0),
        "completion_tokens": int(usage_metadata.get("output_tokens") or 0),
        "cache_read_input_tokens": int(details.get("cache_read") or 0),
        "cache_creation_input_tokens": int(details.get("cache_creation") or 0),
    }
    if current is None:
        return incoming
    return {key: max(current[key], value) for key, value in incoming.items()}


def _add_turn_usage(
    total: dict[str, int] | None, call_usage: dict[str, int] | None
) -> dict[str, int] | None:
    """Add one completed LLM call's usage to the turn total.

    Summed, not maxed: a tool-calling turn bills two separate LLM calls and NGos
    needs the combined cost of the whole turn.
    """
    if call_usage is None:
        return total
    if total is None:
        return dict(call_usage)
    return {key: total[key] + value for key, value in call_usage.items()}


def _partition_input_tokens(usage: dict[str, int]) -> dict[str, int]:
    """Split ``prompt_tokens`` into its three billing classes.

    ``prompt_tokens`` is the inclusive total. The three classes bill at very
    different rates — uncached at 1x, cache reads at 0.1x, cache writes at
    1.25x — so a caller that prices ``prompt_tokens`` at the full input rate and
    *then* adds the cache counts charges the cached tokens twice. Emitting the
    uncached remainder explicitly makes the split additive and self-checking:

        uncached + cache_read + cache_creation == prompt_tokens

    Clamped at zero: the inclusive convention holds for Anthropic and OpenAI
    through LiteLLM, but a provider that reported the cache counts *outside*
    ``prompt_tokens`` would otherwise yield a negative remainder.
    """
    cached = usage["cache_read_input_tokens"] + usage["cache_creation_input_tokens"]
    return {
        **usage,
        "uncached_input_tokens": max(0, usage["prompt_tokens"] - cached),
        "total_tokens": usage["prompt_tokens"] + usage["completion_tokens"],
    }


async def _execute_tool(
    tool_name: str,
    tool_args: dict[str, Any],
    tool_registry: dict[str, BaseTool],
    config: RunnableConfig | None = None,
) -> tuple[str, bool]:
    """Execute a tool and return the result with success status.

    Args:
        tool_name: Name of the tool to execute
        tool_args: Arguments to pass to the tool
        tool_registry: Registry mapping tool names to tool instances
        config: Optional LangChain runnable config (e.g. for tracing callbacks)

    Returns:
        Tuple of (result_string, success_bool)
    """
    if tool_name not in tool_registry:
        return f"Unknown tool: {tool_name}", False

    tool_func = tool_registry[tool_name]
    try:
        result = await tool_func.ainvoke(tool_args, config=config)
        return str(result), True
    except Exception as e:
        # Return the failure as a string so the agentic loop can feed it back to
        # the model and continue, rather than aborting the whole turn. This is
        # essential for network-backed MCP tools, whose transport/connection
        # errors (timeouts, dropped sessions) are expected and recoverable and
        # fall outside the narrow error set the built-in tools stay within.
        logger.exception("Tool execution failed: %s", tool_name)
        return f"Error executing tool: {e}", False


class Agent:
    """
    Agent service for handling LLM interactions with streaming support.

    Uses LiteLLM (via LangChain) for chat completions and tool calling, so any
    LiteLLM-supported provider works. Supports an agentic tool-calling loop with
    user notifications.
    """

    def __init__(
        self,
        vector_database: VectorDatabase | None = None,
        document_repository: DocumentRagRepository | None = None,
        mcp_connections: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """
        Initialize the agent with the configured LLM.

        Args:
            vector_database: VectorDatabase for RAG search (calls sqlite-vec service)
            document_repository: DocumentRagRepository for document knowledge search
            mcp_connections: Remote MCP server connections. Tools are discovered
                per turn (in ``astream``) via a live session so stateful servers
                (e.g. browser automation) retain state across tool calls.
        """
        # Initialize Langfuse tracing (idempotent; also called at app startup)
        init_langfuse()

        self._default_model = resolve_default_model()
        self._base_llm = _build_chat_llm(model=self._default_model)
        self._mcp_connections = mcp_connections or {}

        # Built-in tools depend only on the injected backends and are stable for
        # the agent's lifetime. MCP tools are added per turn (see astream).
        self.tools: list[BaseTool] = []

        if vector_database is not None:
            self.tools.append(Agent._create_rag_tool(vector_database))
            logger.info("Agent initialized with RAG tool")
        else:
            logger.info("Agent initialized without RAG tool")

        if document_repository is not None:
            self.tools.append(Agent._create_document_rag_tool(document_repository))
            logger.info("Agent initialized with document RAG tool")

        # LLM bound to the built-in tools only; used for turns without MCP tools.
        self.llm = self._base_llm.bind_tools(self.tools)
        self.tool_registry: dict[str, BaseTool] = {
            tool.name: tool for tool in self.tools
        }
        self._last_langfuse_handler: CallbackHandler | None = None
        # Token usage and resolved model for the most recent astream() call.
        # Reported to the client on the terminating "end" frame so callers can
        # accrue spend against their own budget.
        self._last_turn_usage: dict[str, int] | None = None
        # Set when any LLM call of the turn reported no usage, which makes the
        # running total an undercount rather than a measurement.
        self._last_turn_usage_partial: bool = False
        self._last_turn_model: str | None = None

    @staticmethod
    def _create_rag_tool(db: VectorDatabase) -> BaseTool:
        """
        Create RAG tool that searches via sqlite-vec database service.

        Args:
            db: The VectorDatabase instance (calls sqlite-vec service via HTTP)

        Returns:
            LangChain tool for semantic search
        """

        @tool
        async def search_products(query: str) -> str:
            """Search the product catalog (semantic / RAG). Use for clothing, shopping, or inventory questions.

            Returns formatted product lines from sqlite-vec, or a short no-match message.
            """
            try:
                search_query = Agent._extract_product_query(query)
                logger.info("RAG searching: '%s' (from: '%s')", search_query, query)

                products = await db.search(query=search_query, limit=10)

                if not products:
                    logger.info("No products found for query")
                    return "No products found matching that description in our current catalog."

                logger.info("RAG retrieved %d products", len(products))
                return str(db.format_products(products))

            except Exception as e:
                logger.exception("RAG search failed")
                return f"Error searching products: {e}"

        return search_products

    @staticmethod
    def _create_document_rag_tool(
        repo: DocumentRagRepository,
    ) -> BaseTool:
        """Create document retrieval tool with citation-numbered output.

        Results are appended to the ``_current_sources`` ContextVar so callers
        can read sources after streaming to build the ``end`` frame payload.
        All chunks from the same document share a single citation number so
        the model references the document as one unit regardless of how many
        chunks were retrieved. Numbers are stable across multi-turn tool calls.
        """

        @tool
        async def search_documents(query: str, limit: int = 5) -> str:
            """Search indexed documents and return snippets with numbered citation references."""
            try:
                sources = _current_sources.get()
                hits = await repo.search(query=query, limit=limit)
                if not hits:
                    return "No relevant documents found."

                # Map source_id → 1-based citation number. All chunks from the
                # same document share one number; documents already tracked from
                # a previous call keep their existing number.
                seen: dict[str, int] = {
                    s["source_id"]: i + 1 for i, s in enumerate(sources)
                }

                snippet_lines: list[str] = []
                meta_lines: list[str] = [
                    "\n---",
                    "Citation metadata (use these numbers for inline references):",
                ]

                for hit in hits:
                    src = hit.source
                    if src.source_id not in seen:
                        sources.append(
                            {
                                "source_id": src.source_id,
                                "source_uri": src.source_uri,
                                "title": src.title,
                                "chunk_id": src.chunk_id,
                                "source_type": src.source_type,
                                "page": src.page,
                            }
                        )
                        seen[src.source_id] = len(sources)

                    num = seen[src.source_id]
                    name = Path(src.source_uri or src.source_id).name
                    page_info = f" (page {src.page})" if src.page is not None else ""
                    snippet_lines.append(f"[{num}]{page_info} {name}:\n{hit.snippet}")

                    page_str = f", page {src.page}" if src.page is not None else ""
                    meta_lines.append(f"- [{num}] {name}{page_str}")

                return "\n\n".join(snippet_lines) + "\n".join(meta_lines)
            except Exception as e:
                logger.exception("Document RAG search failed")
                return f"Error searching documents: {e}"

        return search_documents

    @staticmethod
    def _filter_mcp_tools(
        mcp_tools: list[BaseTool],
        existing_tools: list[BaseTool],
    ) -> list[BaseTool]:
        """Drop MCP tools whose names collide with built-in tools.

        Built-in tools (``search_products``, ``search_documents``) always win so
        a remote MCP server cannot shadow core functionality. Collisions between
        two MCP tools keep the first occurrence.
        """
        taken: set[str] = {existing.name for existing in existing_tools}
        accepted: list[BaseTool] = []
        for mcp_tool in mcp_tools:
            if mcp_tool.name in taken:
                logger.warning(
                    "Skipping MCP tool %r: name collides with an existing tool",
                    mcp_tool.name,
                )
                continue
            taken.add(mcp_tool.name)
            accepted.append(mcp_tool)
        # Runs once per turn (see astream), not at startup — keep at debug so it
        # doesn't spam the logs on every user message.
        logger.debug("Bound %d MCP tool(s) for this turn", len(accepted))
        return accepted

    @staticmethod
    def _extract_product_query(message: str) -> str:
        """Normalize user text into vector-search terms (strip prices, filler, punctuation)."""
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
        """Build LangChain messages: system prompt + full conversation transcript.

        The system prompt is fetched from Langfuse (``CHAT_SYSTEM_PROMPT``) on
        every turn so edits in the Langfuse UI take effect within the SDK
        cache TTL (~60 s) without redeploying.  When Langfuse is unavailable
        the call falls back to ``load_fallback_prompt()`` — the local md file
        configured via ``AGENT_SYSTEM_PROMPT_FALLBACK_FILE`` or, failing that,
        the built-in ``SYSTEM_PROMPT`` (StyleBot) — so the chat surface stays
        functional.
        """
        system_prompt = get_prompt_text(
            CHAT_SYSTEM_PROMPT_NAME, fallback=load_fallback_prompt()
        )
        messages: list[BaseMessage] = [SystemMessage(content=system_prompt.strip())]
        messages.extend(_convert_history_to_messages(transcript))
        return messages

    @property
    def last_trace_id(self) -> str | None:
        """Return the Langfuse trace ID from the most recent ``astream()`` call.

        Returns ``None`` when Langfuse is disabled, not yet initialised, or when
        the handler has not produced a trace ID (e.g. the stream was never consumed).
        """
        if self._last_langfuse_handler is None:
            return None
        return self._last_langfuse_handler.last_trace_id

    @staticmethod
    async def _process_tool_calls(
        full_response: AIMessageChunk | AIMessage,
        messages: list[BaseMessage],
        tool_registry: dict[str, BaseTool],
        config: RunnableConfig | None = None,
    ) -> None:
        """Execute tool calls and append results to messages."""
        logger.info("Processing %d tool call(s)", len(full_response.tool_calls))
        messages.append(full_response)

        for tool_call in full_response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_call_id = tool_call["id"]

            result, _ = await _execute_tool(
                tool_name, tool_args, tool_registry, config=config
            )
            messages.append(ToolMessage(content=result, tool_call_id=tool_call_id))

    @asynccontextmanager
    async def _tracing_context(
        self,
        *,
        session_id: str | None,
        visitor_id: str | None,
        input_value: Any,
    ) -> AsyncIterator[tuple[RunnableConfig, list[str]]]:
        """Yield the LangChain ``RunnableConfig`` plus an output accumulator.

        Opens a Langfuse "chat-response" span and wires a fresh
        ``CallbackHandler`` into the config when Langfuse is initialised;
        yields an empty config otherwise.

        The root ``chat-response`` span drives the trace's displayed
        input/output, but the nested ``CallbackHandler`` generations never set
        it. So the caller appends every streamed chunk to the yielded list and,
        on exit, its text plus ``input_value`` are written to the span and trace
        — otherwise the trace shows blank input/output in the Langfuse UI.
        """
        output_chunks: list[str] = []
        if not is_langfuse_initialized():
            yield {}, output_chunks
            return

        langfuse = get_client()
        with (
            langfuse.start_as_current_observation(
                as_type="span",
                name="chat-response",
                input=input_value,
            ) as span,
            propagate_attributes(
                trace_name="chat-response",
                session_id=session_id,
                user_id=visitor_id,
            ),
        ):
            handler = CallbackHandler()
            self._last_langfuse_handler = handler
            try:
                yield {"callbacks": [handler]}, output_chunks
            finally:
                output_text = "".join(output_chunks)
                span.update(output=output_text)
                langfuse.set_current_trace_io(input=input_value, output=output_text)
                await flush_langfuse_async()

    async def astream(
        self,
        messages: list[dict[str, str]],
        *,
        session_id: str | None = None,
        visitor_id: str | None = None,
        model: str | None = None,
        auth_token: str | None = None,
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
            model: Optional LiteLLM model ID to use for this request. When set,
                overrides the agent's default model for this turn.
            auth_token: Optional per-user token forwarded to MCP servers whose
                headers reference ``${user_token}`` (see ``open_mcp_tools``).

        Yields:
            Response chunks as strings (including tool call notifications)
        """
        self._last_langfuse_handler = None
        self._last_turn_usage = None
        self._last_turn_usage_partial = False
        lc_messages = Agent._build_messages_from_transcript(messages)
        # Each astream() call gets a fresh, task-local source list via ContextVar.
        turn_sources: list[dict[str, Any]] = []
        self._last_turn_sources = turn_sources
        _current_sources.set(turn_sources)

        # Resolve the base LLM for this turn: honor a per-request model override,
        # otherwise reuse the agent's pre-built default base LLM.
        base_llm = (
            _build_chat_llm(model=model)
            if model and model != self._default_model
            else self._base_llm
        )
        # The model actually sent to the provider. Not `self._default_model`,
        # which is None in multi-model picker mode (ChatLiteLLM then falls back
        # to LLM_MODEL from settings).
        turn_model = getattr(base_llm, "model", None)
        self._last_turn_model = turn_model

        # Open MCP sessions for the whole turn so stateful servers keep state
        # across tool calls; sessions close when this block exits.
        async with (
            open_mcp_tools(self._mcp_connections, user_token=auth_token) as mcp_tools,
            self._tracing_context(
                session_id=session_id,
                visitor_id=visitor_id,
                input_value=_build_trace_input(messages),
            ) as (config, output_chunks),
        ):
            accepted = Agent._filter_mcp_tools(mcp_tools, self.tools)
            turn_llm, turn_registry = self._bind_turn_tools(base_llm, accepted)
            # Tell the model about the MCP tools it actually has this turn. The
            # base system prompt (managed in Langfuse) only knows the built-in
            # tools, so without this the model may claim it lacks a capability
            # (e.g. web browsing) even though the tool is bound.
            turn_messages = Agent._augment_system_prompt(lc_messages, accepted)
            # Applied last so the cache breakpoint sits at the end of the final
            # system prompt text, tool block included.
            turn_messages = _apply_prompt_cache(turn_messages, turn_model)
            async for chunk in self._run_agentic_loop(
                turn_messages, config, turn_llm, turn_registry
            ):
                # Accumulate for the trace-level output written on context exit.
                output_chunks.append(chunk)
                yield chunk

    def _bind_turn_tools(
        self, base_llm: BaseChatModel, accepted_mcp_tools: list[BaseTool]
    ) -> tuple[Runnable[Any, BaseMessage], dict[str, BaseTool]]:
        """Combine built-in and (already filtered) MCP tools for a turn.

        ``base_llm`` is the LLM to bind against — either the agent's default
        base LLM or a per-request model override. Returns the bound LLM + tool
        registry. When there are no MCP tools and the turn uses the default
        model, reuses the pre-bound built-in LLM so those turns incur no extra
        binding work.
        """
        if not accepted_mcp_tools:
            if base_llm is self._base_llm:
                return self.llm, self.tool_registry
            return base_llm.bind_tools(self.tools), self.tool_registry
        turn_tools = [*self.tools, *accepted_mcp_tools]
        return (
            base_llm.bind_tools(turn_tools),
            {tool.name: tool for tool in turn_tools},
        )

    @staticmethod
    def _augment_system_prompt(
        messages: list[BaseMessage],
        mcp_tools: list[BaseTool],
    ) -> list[BaseMessage]:
        """Tell the model it has extra MCP tools bound for this turn.

        Returns ``messages`` unchanged when there are no MCP tools or no system
        message. Otherwise returns a new list with the leading system message
        extended by a short capability note.

        Deliberately does NOT enumerate the tools. Their names, descriptions and
        parameter schemas already reach the model through the provider's
        ``tools`` parameter (see ``_bind_turn_tools``), so listing them here was
        a strictly lossier second copy of the same text — with 40 MCP tools that
        duplicated ~6.3k characters into every LLM call. Only the framing is
        kept, because the base system prompt (managed in Langfuse) knows just
        the built-in tools and without this the model would sometimes deny a
        capability it actually has.
        """
        if not mcp_tools or not messages:
            return messages
        head = messages[0]
        if not isinstance(head, SystemMessage):
            return messages

        block = (
            "\n\n---\n"
            "ADDITIONAL TOOLS AVAILABLE THIS TURN:\n"
            "Beyond the tools described above, you have direct access to tools "
            "provided by connected MCP servers. Use them whenever the request "
            "calls for them. Do NOT claim you lack a capability that these "
            "tools provide — call the appropriate tool instead."
        )
        base = head.content if isinstance(head.content, str) else str(head.content)
        return [SystemMessage(content=base + block), *messages[1:]]

    async def _run_agentic_loop(
        self,
        messages: list[BaseMessage],
        config: RunnableConfig,
        llm: Runnable[Any, BaseMessage],
        tool_registry: dict[str, BaseTool],
    ) -> AsyncIterator[str]:
        """Run the agentic loop until no more tool calls or max iterations."""
        for iteration in range(MAX_TOOL_ITERATIONS):
            full_response: AIMessageChunk | None = None
            call_usage: dict[str, int] | None = None

            async for chunk in llm.astream(messages, config=config):
                chunk_msg = chunk if isinstance(chunk, AIMessageChunk) else None
                if chunk_msg:
                    full_response = (
                        chunk_msg
                        if full_response is None
                        else full_response + chunk_msg
                    )
                    # Read usage off the raw chunk, not the accumulated
                    # `full_response`, whose `+` sums usage across chunks and so
                    # would double-count Anthropic's two usage reports per call.
                    call_usage = _merge_call_usage(call_usage, chunk_msg.usage_metadata)

                content: Any = getattr(chunk, "content", "")
                if content:
                    yield str(content)

            if call_usage is None:
                # A partial total is indistinguishable from a complete one, so
                # it would be accrued as truth and silently undercharge the
                # turn. Flag it and report the whole turn as unknown instead.
                self._last_turn_usage_partial = True
                logger.warning(
                    "LLM call %d of the turn reported no token usage; "
                    "turn usage will be reported as unknown",
                    iteration + 1,
                )
            self._last_turn_usage = _add_turn_usage(self._last_turn_usage, call_usage)

            if full_response is None or not full_response.tool_calls:
                logger.info("Agentic loop completed after %d iterations", iteration + 1)
                return

            await self._process_tool_calls(
                full_response, messages, tool_registry, config=config
            )
        logger.warning("Reached maximum tool iterations (%d)", MAX_TOOL_ITERATIONS)
        yield "\n\n⚠️ Reached maximum tool call limit. Please rephrase your question."

    def get_last_used_sources(self) -> list[dict[str, Any]]:
        """Return structured sources collected during the most recent astream() call."""
        return list(getattr(self, "_last_turn_sources", []))

    def get_last_usage(self) -> dict[str, int] | None:
        """Return token usage for the most recent ``astream()`` call.

        Counts are summed across every LLM call the agentic loop made, so a
        tool-calling turn reports the whole turn's cost. Returns ``None`` when
        the usage of the turn is not fully known — either no call reported any,
        or *some* call didn't — which callers must treat as "unknown" rather
        than zero. All-or-nothing on purpose: a total missing one call's tokens
        looks exactly like a complete one, so a caller accruing spend would
        undercharge the turn with no way to notice.

        ``prompt_tokens`` is the inclusive input total; ``uncached_input_tokens``,
        ``cache_read_input_tokens`` and ``cache_creation_input_tokens`` partition
        it. Price the three parts, not ``prompt_tokens`` plus the cache counts.
        """
        usage = getattr(self, "_last_turn_usage", None)
        if usage is None or getattr(self, "_last_turn_usage_partial", False):
            return None
        return _partition_input_tokens(usage)

    @property
    def last_model(self) -> str | None:
        """Return the model id used for the most recent ``astream()`` call."""
        return getattr(self, "_last_turn_model", None)
