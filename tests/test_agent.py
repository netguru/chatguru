"""Agent component tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessageChunk, BaseMessage
from langchain_core.messages.ai import UsageMetadata

from src.agent.service import Agent


class _FakeDocumentRepository:
    async def connect(self) -> None:
        return

    async def search(self, query: str, limit: int = 5) -> list:
        from document_rag.models import DocumentRetrievalHit, DocumentSourceReference

        return [
            DocumentRetrievalHit(
                snippet=f"Snippet for {query}",
                score=0.91,
                source=DocumentSourceReference(
                    source_id="doc-42",
                    source_uri="docs/guide.md",
                    title="Guide",
                ),
            )
        ]

    async def close(self) -> None:
        return


def test_create_agent() -> None:
    """Test that the agent is created correctly."""
    with patch("src.agent.service._build_chat_llm") as mock_build:
        mock_instance = GenericFakeChatModel(messages=iter([]))
        # Use object.__setattr__ to bypass Pydantic validation
        # bind_tools should return self for method chaining
        object.__setattr__(mock_instance, "bind_tools", lambda tools: mock_instance)
        mock_build.return_value = mock_instance
        agent = Agent()
        assert agent is not None


@pytest.mark.asyncio
async def test_agent_astream() -> None:
    """Test the agent astream method with streaming chunks."""
    chunks = ["Hello", " ", "world", "!"]

    async def mock_astream(
        messages: list, *, config: dict | None = None
    ) -> AsyncIterator[AIMessageChunk]:
        for chunk in chunks:
            # AIMessageChunk without tool_calls will end the agentic loop
            mock_chunk = AIMessageChunk(content=chunk)
            yield mock_chunk

    with patch("src.agent.service._build_chat_llm") as mock_build:
        mock_instance = GenericFakeChatModel(messages=iter([]))
        # Use object.__setattr__ to bypass Pydantic validation
        object.__setattr__(mock_instance, "bind_tools", lambda tools: mock_instance)
        object.__setattr__(mock_instance, "astream", mock_astream)
        mock_build.return_value = mock_instance
        agent = Agent()

        received_chunks = []
        async for chunk in agent.astream([{"role": "user", "content": "Hello"}]):
            received_chunks.append(chunk)

        assert len(received_chunks) == len(chunks)
        assert "".join(received_chunks) == "".join(chunks)


@pytest.mark.asyncio
async def test_agent_astream_empty_response() -> None:
    """Test the agent astream method with empty response."""

    async def mock_astream(
        messages: list, *, config: dict | None = None
    ) -> AsyncIterator[AIMessageChunk]:
        # Yield empty content (should be filtered out)
        mock_chunk = AIMessageChunk(content="")
        yield mock_chunk

    with patch("src.agent.service._build_chat_llm") as mock_build:
        mock_instance = GenericFakeChatModel(messages=iter([]))
        # Use object.__setattr__ to bypass Pydantic validation
        object.__setattr__(mock_instance, "bind_tools", lambda tools: mock_instance)
        object.__setattr__(mock_instance, "astream", mock_astream)
        mock_build.return_value = mock_instance
        agent = Agent()

        received_chunks = []
        async for chunk in agent.astream([{"role": "user", "content": "Hello"}]):
            received_chunks.append(chunk)

        # Empty content should be filtered out
        assert len(received_chunks) == 0


@pytest.mark.asyncio
async def test_agent_astream_single_chunk() -> None:
    """Test the agent astream method with a single chunk."""

    async def mock_astream(
        messages: list, *, config: dict | None = None
    ) -> AsyncIterator[AIMessageChunk]:
        mock_chunk = AIMessageChunk(content="Single response")
        yield mock_chunk

    with patch("src.agent.service._build_chat_llm") as mock_build:
        mock_instance = GenericFakeChatModel(messages=iter([]))
        # Use object.__setattr__ to bypass Pydantic validation
        object.__setattr__(mock_instance, "bind_tools", lambda tools: mock_instance)
        object.__setattr__(mock_instance, "astream", mock_astream)
        mock_build.return_value = mock_instance
        agent = Agent()

        received_chunks = []
        async for chunk in agent.astream([{"role": "user", "content": "Hello"}]):
            received_chunks.append(chunk)

        assert len(received_chunks) == 1
        assert received_chunks[0] == "Single response"


@pytest.mark.asyncio
async def test_agent_with_tool_call() -> None:
    """Test the agent astream method with tool calling."""
    call_count = {"count": 0}

    async def mock_astream(
        messages: list, *, config: dict | None = None
    ) -> AsyncIterator[AIMessageChunk]:
        call_count["count"] += 1
        if call_count["count"] == 1:
            # First call: LLM wants to call a tool
            chunk1 = AIMessageChunk(content="Let me search for that...")
            chunk1.tool_calls = [
                {
                    "name": "search_products",
                    "args": {"query": "red jeans"},
                    "id": "call_123",
                }
            ]
            yield chunk1
        else:
            # Second call: LLM provides final answer after tool execution
            chunk2 = AIMessageChunk(content="Here are the results!")
            yield chunk2

    # Mock VectorDatabase
    mock_db = MagicMock()
    mock_db.search = AsyncMock(return_value=[])
    mock_db.search.return_value = []
    mock_db.format_products.return_value = "No products found."

    with patch("src.agent.service._build_chat_llm") as mock_build:
        mock_instance = GenericFakeChatModel(messages=iter([]))
        # Use object.__setattr__ to bypass Pydantic validation
        object.__setattr__(mock_instance, "bind_tools", lambda tools: mock_instance)
        object.__setattr__(mock_instance, "astream", mock_astream)
        mock_build.return_value = mock_instance
        agent = Agent(vector_database=mock_db)

        received_chunks = []
        async for chunk in agent.astream(
            [{"role": "user", "content": "Show me red jeans"}]
        ):
            received_chunks.append(chunk)

        # Verify the agentic loop worked correctly
        full_response = "".join(received_chunks)
        # Should have initial response and final response
        assert "Let me search for that..." in full_response
        assert "Here are the results!" in full_response
        # Verify the database search was actually invoked (tool was executed)
        mock_db.search.assert_called_once()
        # Verify we got multiple iterations (initial + after tool call)
        assert call_count["count"] == 2


@pytest.mark.asyncio
async def test_document_tool_returns_snippet_with_source_reference() -> None:
    from src.agent.service import _current_sources

    sources: list[dict] = []
    _current_sources.set(sources)
    tool = Agent._create_document_rag_tool(_FakeDocumentRepository())
    result = await tool.ainvoke({"query": "install"})
    assert "Snippet for install" in result
    assert "[1]" in result
    assert "guide.md" in result
    # Source should be tracked with the correct metadata
    assert len(sources) == 1
    assert sources[0]["source_id"] == "doc-42"
    assert sources[0]["source_uri"] == "docs/guide.md"


@pytest.mark.asyncio
async def test_agent_collects_structured_sources_from_document_tool() -> None:
    call_count = {"count": 0}

    async def mock_astream(
        messages: list, *, config: dict | None = None
    ) -> AsyncIterator[AIMessageChunk]:
        call_count["count"] += 1
        if call_count["count"] == 1:
            chunk = AIMessageChunk(content="Checking docs...")
            chunk.tool_calls = [
                {
                    "name": "search_documents",
                    "args": {"query": "setup", "limit": 3},
                    "id": "doc_call_1",
                }
            ]
            yield chunk
        else:
            yield AIMessageChunk(content="Done")

    with patch("src.agent.service._build_chat_llm") as mock_build:
        mock_instance = GenericFakeChatModel(messages=iter([]))
        object.__setattr__(mock_instance, "bind_tools", lambda tools: mock_instance)
        object.__setattr__(mock_instance, "astream", mock_astream)
        mock_build.return_value = mock_instance
        agent = Agent(document_repository=_FakeDocumentRepository())

        _ = [
            chunk
            async for chunk in agent.astream([{"role": "user", "content": "help"}])
        ]

    sources = agent.get_last_used_sources()
    assert len(sources) == 1
    assert sources[0]["source_id"] == "doc-42"


@pytest.mark.asyncio
async def test_last_trace_id_is_none_without_langfuse() -> None:
    """last_trace_id returns None when Langfuse is not initialised."""

    async def mock_astream(
        messages: list, *, config: dict | None = None
    ) -> AsyncIterator[AIMessageChunk]:
        yield AIMessageChunk(content="Hi")

    with patch("src.agent.service._build_chat_llm") as mock_build:
        mock_instance = GenericFakeChatModel(messages=iter([]))
        object.__setattr__(mock_instance, "bind_tools", lambda tools: mock_instance)
        object.__setattr__(mock_instance, "astream", mock_astream)
        mock_build.return_value = mock_instance

        agent = Agent()
        async for _ in agent.astream([{"role": "user", "content": "Hello"}]):
            pass
        assert agent.last_trace_id is None


@pytest.mark.asyncio
async def test_last_trace_id_resets_between_calls() -> None:
    """last_trace_id is reset to None at the start of each astream() call."""

    async def mock_astream(
        messages: list, *, config: dict | None = None
    ) -> AsyncIterator[AIMessageChunk]:
        yield AIMessageChunk(content="Hi")

    handlers = [
        MagicMock(last_trace_id="trace-first"),
        MagicMock(last_trace_id=None),
    ]

    @asynccontextmanager
    async def fake_tracing_context(
        self: Agent,
        *,
        session_id: str | None,
        visitor_id: str | None,
        input_value: object,
    ) -> AsyncIterator[tuple[dict, list[str]]]:
        self._last_langfuse_handler = handlers.pop(0)
        yield {}, []

    with patch("src.agent.service._build_chat_llm") as mock_build:
        mock_instance = GenericFakeChatModel(messages=iter([]))
        object.__setattr__(mock_instance, "bind_tools", lambda tools: mock_instance)
        object.__setattr__(mock_instance, "astream", mock_astream)
        mock_build.return_value = mock_instance

        with patch.object(Agent, "_tracing_context", fake_tracing_context):
            agent = Agent()

            async for _ in agent.astream([{"role": "user", "content": "Hello"}]):
                pass
            assert agent.last_trace_id == "trace-first"

            async for _ in agent.astream([{"role": "user", "content": "Hello"}]):
                pass
            assert agent.last_trace_id is None


@pytest.mark.asyncio
async def test_astream_populates_trace_input_and_output() -> None:
    """The chat-response trace records the conversation input and streamed output.

    Regression test: the root ``chat-response`` span (which drives the trace's
    displayed input/output) was created empty, so Langfuse traces showed no
    input or output even though nested generations had data.
    """
    chunks = ["Hello", " ", "world"]

    async def mock_astream(
        messages: list, *, config: dict | None = None
    ) -> AsyncIterator[AIMessageChunk]:
        for chunk in chunks:
            yield AIMessageChunk(content=chunk)

    mock_langfuse = MagicMock()

    with (
        patch("src.agent.service._build_chat_llm") as mock_build,
        patch("src.agent.service.is_langfuse_initialized", return_value=True),
        patch("src.agent.service.get_client", return_value=mock_langfuse),
        patch("src.agent.service.CallbackHandler", return_value=MagicMock()),
        patch("src.agent.service.propagate_attributes", MagicMock()),
        patch("src.agent.service.flush_langfuse_async", new=AsyncMock()),
    ):
        mock_instance = GenericFakeChatModel(messages=iter([]))
        object.__setattr__(mock_instance, "bind_tools", lambda tools: mock_instance)
        object.__setattr__(mock_instance, "astream", mock_astream)
        mock_build.return_value = mock_instance

        agent = Agent()
        async for _ in agent.astream([{"role": "user", "content": "Hi there"}]):
            pass

    # Root span created with the conversation transcript as its input.
    obs_kwargs = mock_langfuse.start_as_current_observation.call_args.kwargs
    assert obs_kwargs["name"] == "chat-response"
    assert "Hi there" in str(obs_kwargs["input"])

    # Trace-level input/output populated so the Langfuse UI is not blank.
    trace_kwargs = mock_langfuse.set_current_trace_io.call_args.kwargs
    assert "Hi there" in str(trace_kwargs["input"])
    assert trace_kwargs["output"] == "Hello world"


def test_agent_registers_both_document_and_product_tools() -> None:
    mock_db = MagicMock()
    with patch("src.agent.service._build_chat_llm") as mock_build:
        mock_instance = GenericFakeChatModel(messages=iter([]))
        object.__setattr__(mock_instance, "bind_tools", lambda tools: mock_instance)
        mock_build.return_value = mock_instance

        agent = Agent(
            vector_database=mock_db,
            document_repository=_FakeDocumentRepository(),
        )

    assert "search_products" in agent.tool_registry
    assert "search_documents" in agent.tool_registry


class TestExtractProductQuery:
    """Test suite for _extract_product_query method."""

    def test_documented_examples(self) -> None:
        """Test the documented examples from the docstring."""
        assert Agent._extract_product_query("gloves under 50$") == "gloves"
        assert Agent._extract_product_query("blue jeans less than 100") == "blue jeans"
        assert Agent._extract_product_query("show me affordable shirts") == "shirts"

    def test_price_constraints_removal(self) -> None:
        """Test removal of various price constraint patterns."""
        # Test "under" pattern
        assert Agent._extract_product_query("jackets under $100") == "jackets"
        assert Agent._extract_product_query("shoes under 50$") == "shoes"
        assert Agent._extract_product_query("pants under 75") == "pants"

        # Test "less than" pattern
        assert Agent._extract_product_query("shirts less than $30") == "shirts"
        assert Agent._extract_product_query("socks less than 20$") == "socks"

        # Test "below" pattern
        assert Agent._extract_product_query("hats below $25") == "hats"
        assert Agent._extract_product_query("scarves below 15") == "scarves"

        # Test "cheaper than" pattern
        assert Agent._extract_product_query("gloves cheaper than $40") == "gloves"

        # Test "more than" pattern
        assert Agent._extract_product_query("coats more than $150") == "coats"

        # Test "above" pattern
        assert Agent._extract_product_query("suits above $200") == "suits"

    def test_price_value_removal(self) -> None:
        """Test removal of standalone price values."""
        assert Agent._extract_product_query("red dress $99") == "red dress"
        assert Agent._extract_product_query("sneakers $75 please") == "sneakers"
        assert Agent._extract_product_query("$50 t-shirts") == "t-shirts"

    def test_affordability_words_removal(self) -> None:
        """Test removal of affordability-related words."""
        assert Agent._extract_product_query("affordable winter coats") == "winter coats"
        assert Agent._extract_product_query("cheap running shoes") == "running shoes"
        assert (
            Agent._extract_product_query("expensive leather boots") == "leather boots"
        )
        assert Agent._extract_product_query("budget friendly jeans") == "friendly jeans"

    def test_question_words_removal(self) -> None:
        """Test removal of common question/request phrases."""
        assert Agent._extract_product_query("do you have blue shirts") == "blue shirts"
        assert Agent._extract_product_query("show me red dresses") == "red dresses"
        assert (
            Agent._extract_product_query("looking for winter gloves") == "winter gloves"
        )
        assert Agent._extract_product_query("i need black pants") == "black pants"
        assert Agent._extract_product_query("i want casual shoes") == "casual shoes"
        assert Agent._extract_product_query("what about summer hats") == "summer hats"

    def test_case_insensitivity(self) -> None:
        """Test that method handles different cases correctly."""
        assert Agent._extract_product_query("BLUE JEANS") == "blue jeans"
        assert Agent._extract_product_query("Red Shirts") == "red shirts"
        assert Agent._extract_product_query("WiNtEr CoAtS") == "winter coats"

    def test_whitespace_normalization(self) -> None:
        """Test that extra whitespace is normalized."""
        assert Agent._extract_product_query("blue    jeans") == "blue jeans"
        assert Agent._extract_product_query("  red   shirts  ") == "red shirts"
        assert Agent._extract_product_query("winter\t\tcoats") == "winter coats"

    def test_combined_patterns(self) -> None:
        """Test queries with multiple patterns combined."""
        assert (
            Agent._extract_product_query("show me affordable blue jeans under $50")
            == "blue jeans"
        )
        assert (
            Agent._extract_product_query("do you have cheap red shirts less than $20")
            == "red shirts"
        )
        assert (
            Agent._extract_product_query("i need expensive leather jackets above $200")
            == "leather jackets"
        )
        assert (
            Agent._extract_product_query("looking for budget winter coats under 100$")
            == "winter coats"
        )

    def test_preserves_important_attributes(self) -> None:
        """Test that important product attributes are preserved."""
        # Colors should be preserved
        assert (
            Agent._extract_product_query("red leather jacket") == "red leather jacket"
        )
        assert Agent._extract_product_query("blue cotton shirt") == "blue cotton shirt"

        # Materials should be preserved
        assert Agent._extract_product_query("wool winter coat") == "wool winter coat"
        assert (
            Agent._extract_product_query("silk evening dress") == "silk evening dress"
        )

        # Styles should be preserved
        assert (
            Agent._extract_product_query("casual summer pants") == "casual summer pants"
        )
        assert (
            Agent._extract_product_query("formal business suit")
            == "formal business suit"
        )

    def test_edge_cases(self) -> None:
        """Test edge cases and boundary conditions."""
        # Empty string handling (returns original message as fallback)
        assert Agent._extract_product_query("") == ""

        # Single word
        assert Agent._extract_product_query("shoes") == "shoes"

        # Only stopwords (should return original as fallback)
        result = Agent._extract_product_query("show me")
        assert result == "show me"  # Returns original when result would be empty

        # Numbers without price context should be preserved
        assert Agent._extract_product_query("size 10 shoes") == "size 10 shoes"

        # Multiple price mentions
        assert (
            Agent._extract_product_query("shirts under $30 or less than $40")
            == "shirts or"
        )

    def test_real_world_queries(self) -> None:
        """Test realistic user queries."""
        # All filler words and price info removed
        assert (
            Agent._extract_product_query(
                "I'm looking for affordable winter gloves under $50"
            )
            == "winter gloves"
        )

        # All filler words, question words, and price info removed
        assert (
            Agent._extract_product_query(
                "Do you have any blue jeans less than 100 dollars?"
            )
            == "blue jeans"
        )

        # "show me" removed, rest remains
        assert (
            Agent._extract_product_query("Show me your best running shoes")
            == "your best running shoes"
        )

        # "what about" and "cheap" removed, punctuation removed
        assert (
            Agent._extract_product_query("What about cheap leather jackets?")
            == "leather jackets"
        )

        # "i need" removed, articles remain
        assert (
            Agent._extract_product_query("I need a red dress for a party under $80")
            == "a red dress for a party"
        )

    def test_fallback_to_original(self) -> None:
        """Test that method falls back to original message when extraction results in empty string."""
        # Query that would result in empty string should return original
        original = "under $50"
        result = Agent._extract_product_query(original)
        assert result == original

        original = "affordable"
        result = Agent._extract_product_query(original)
        assert result == original


# --- prompt caching --------------------------------------------------------


class TestPromptCache:
    """Anthropic prompt-cache breakpoint on the stable system prefix."""

    def test_marks_system_prompt_for_anthropic(self) -> None:
        from langchain_core.messages import HumanMessage, SystemMessage

        from src.agent.service import _apply_prompt_cache

        messages: list[BaseMessage] = [
            SystemMessage(content="Persona."),
            HumanMessage(content="hi"),
        ]
        cached = _apply_prompt_cache(messages, "anthropic/claude-sonnet-4-6")

        assert cached[0].content == [
            {
                "type": "text",
                "text": "Persona.",
                "cache_control": {"type": "ephemeral"},
            }
        ]
        # Conversation is untouched, so per-turn grounding never invalidates it.
        assert cached[1] is messages[1]
        assert messages[0].content == "Persona."

    @pytest.mark.parametrize(
        "model",
        [
            "anthropic/claude-sonnet-4-6",
            "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
            "vertex_ai/claude-opus-4",
        ],
    )
    def test_applies_to_every_anthropic_route(self, model: str) -> None:
        from langchain_core.messages import SystemMessage

        from src.agent.service import _apply_prompt_cache

        messages: list[BaseMessage] = [SystemMessage(content="Persona.")]
        cached = _apply_prompt_cache(messages, model)
        assert isinstance(cached[0].content, list)

    @pytest.mark.parametrize(
        "model",
        [
            "openai/gpt-5-mini",
            "azure/gpt-4o",
            # "claude" in the model half of a non-Anthropic route: an operator
            # -named Azure deployment or gateway alias. `cache_control` content
            # would reach a provider that does not accept it.
            "azure/claude-sonnet-proxy",
            "openai/claude-compat",
            # Bedrock and Vertex also serve models that aren't Claude.
            "bedrock/meta.llama3-70b-instruct-v1:0",
            "vertex_ai/gemini-2.0-flash",
            "",
            None,
        ],
    )
    def test_noop_for_non_anthropic_models(self, model: str | None) -> None:
        from langchain_core.messages import SystemMessage

        from src.agent.service import _apply_prompt_cache

        messages: list[BaseMessage] = [SystemMessage(content="Persona.")]
        assert _apply_prompt_cache(messages, model) is messages

    def test_noop_when_system_content_already_structured(self) -> None:
        """Never reshape content this function did not build."""
        from langchain_core.messages import SystemMessage

        from src.agent.service import _apply_prompt_cache

        messages: list[BaseMessage] = [
            SystemMessage(content=[{"type": "text", "text": "Persona."}])
        ]
        assert _apply_prompt_cache(messages, "anthropic/claude-sonnet-4-6") is messages

    def test_noop_without_leading_system_message(self) -> None:
        from langchain_core.messages import HumanMessage

        from src.agent.service import _apply_prompt_cache

        messages: list[BaseMessage] = [HumanMessage(content="hi")]
        assert _apply_prompt_cache(messages, "anthropic/claude-sonnet-4-6") is messages


# --- token usage accounting ------------------------------------------------


def _usage(inp: int, out: int, read: int = 0, write: int = 0) -> UsageMetadata:
    return UsageMetadata(
        input_tokens=inp,
        output_tokens=out,
        total_tokens=inp + out,
        input_token_details={"cache_read": read, "cache_creation": write},
    )


class TestUsageAccounting:
    def test_merge_takes_field_wise_max_within_one_call(self) -> None:
        """LiteLLM reports Anthropic usage twice per call as cumulative snapshots.

        message_start carries input + cache counts, message_delta carries the
        output count. Summing them would double-count the input tokens.
        """
        from src.agent.service import _merge_call_usage

        merged = _merge_call_usage(None, _usage(12000, 0, read=11800))
        merged = _merge_call_usage(merged, _usage(12000, 350, read=11800))

        assert merged == {
            "prompt_tokens": 12000,
            "completion_tokens": 350,
            "cache_read_input_tokens": 11800,
            "cache_creation_input_tokens": 0,
        }

    def test_merge_ignores_chunks_without_usage(self) -> None:
        from src.agent.service import _merge_call_usage

        assert _merge_call_usage(None, None) is None
        existing = _merge_call_usage(None, _usage(10, 2))
        assert _merge_call_usage(existing, None) == existing

    def test_turn_total_sums_across_llm_calls(self) -> None:
        """A tool-calling turn bills two separate calls; NGos needs the total."""
        from src.agent.service import _add_turn_usage, _merge_call_usage

        first = _merge_call_usage(None, _usage(12000, 50, write=11800))
        second = _merge_call_usage(None, _usage(12400, 300, read=11800))

        total = _add_turn_usage(None, first)
        total = _add_turn_usage(total, second)

        assert total == {
            "prompt_tokens": 24400,
            "completion_tokens": 350,
            "cache_read_input_tokens": 11800,
            "cache_creation_input_tokens": 11800,
        }


@pytest.mark.asyncio
async def test_astream_records_usage_across_tool_calling_turn() -> None:
    """Usage from both LLM calls of a tool-calling turn reaches get_last_usage()."""
    call_count = {"count": 0}

    async def mock_astream(
        messages: list, *, config: dict | None = None
    ) -> AsyncIterator[AIMessageChunk]:
        call_count["count"] += 1
        if call_count["count"] == 1:
            # Real streaming shape: tool calls arrive as tool_call_chunks, which
            # survive chunk addition (a bare `.tool_calls` assignment does not).
            yield AIMessageChunk(
                content="Looking that up...",
                tool_call_chunks=[
                    {
                        "name": "search_products",
                        "args": '{"query": "x"}',
                        "id": "call_1",
                        "index": 0,
                    }
                ],
                # Anthropic reports usage twice per call, cumulatively.
                usage_metadata=_usage(12000, 0, write=11800),
            )
            yield AIMessageChunk(
                content="", usage_metadata=_usage(12000, 50, write=11800)
            )
        else:
            yield AIMessageChunk(content="Done.")
            yield AIMessageChunk(
                content="", usage_metadata=_usage(12400, 300, read=11800)
            )

    mock_db = MagicMock()
    mock_db.search = AsyncMock(return_value=[])
    mock_db.format_products.return_value = "No products found."

    with patch("src.agent.service._build_chat_llm") as mock_build:
        mock_instance = GenericFakeChatModel(messages=iter([]))
        object.__setattr__(mock_instance, "bind_tools", lambda tools: mock_instance)
        object.__setattr__(mock_instance, "astream", mock_astream)
        mock_build.return_value = mock_instance
        agent = Agent(vector_database=mock_db)

        async for _ in agent.astream([{"role": "user", "content": "hi"}]):
            pass

    assert agent.get_last_usage() == {
        "prompt_tokens": 24400,
        "uncached_input_tokens": 24400 - 11800 - 11800,
        "cache_read_input_tokens": 11800,
        "cache_creation_input_tokens": 11800,
        "completion_tokens": 350,
        "total_tokens": 24750,
    }


@pytest.mark.asyncio
async def test_astream_reports_no_usage_when_provider_omits_it() -> None:
    """Absent usage must stay None, never be reported as a free turn."""

    async def mock_astream(
        messages: list, *, config: dict | None = None
    ) -> AsyncIterator[AIMessageChunk]:
        yield AIMessageChunk(content="Hello")

    with patch("src.agent.service._build_chat_llm") as mock_build:
        mock_instance = GenericFakeChatModel(messages=iter([]))
        object.__setattr__(mock_instance, "bind_tools", lambda tools: mock_instance)
        object.__setattr__(mock_instance, "astream", mock_astream)
        mock_build.return_value = mock_instance
        agent = Agent()

        async for _ in agent.astream([{"role": "user", "content": "hi"}]):
            pass

    assert agent.get_last_usage() is None


@pytest.mark.asyncio
async def test_astream_reports_no_usage_when_one_call_of_the_turn_omits_it() -> None:
    """A total missing one call's tokens is reported as unknown, not as the turn.

    Partial and complete totals are indistinguishable to the client, so a
    caller accruing spend would silently undercharge the turn.
    """
    call_count = {"count": 0}

    async def mock_astream(
        messages: list, *, config: dict | None = None
    ) -> AsyncIterator[AIMessageChunk]:
        call_count["count"] += 1
        if call_count["count"] == 1:
            yield AIMessageChunk(
                content="Looking that up...",
                tool_call_chunks=[
                    {
                        "name": "search_products",
                        "args": '{"query": "x"}',
                        "id": "call_1",
                        "index": 0,
                    }
                ],
                usage_metadata=_usage(12000, 50, write=11800),
            )
        else:
            # Second call streams an answer but reports no usage.
            yield AIMessageChunk(content="Done.")

    mock_db = MagicMock()
    mock_db.search = AsyncMock(return_value=[])
    mock_db.format_products.return_value = "No products found."

    with patch("src.agent.service._build_chat_llm") as mock_build:
        mock_instance = GenericFakeChatModel(messages=iter([]))
        object.__setattr__(mock_instance, "bind_tools", lambda tools: mock_instance)
        object.__setattr__(mock_instance, "astream", mock_astream)
        mock_build.return_value = mock_instance
        agent = Agent(vector_database=mock_db)

        async for _ in agent.astream([{"role": "user", "content": "hi"}]):
            pass

    assert call_count["count"] == 2
    assert agent.get_last_usage() is None


@pytest.mark.asyncio
async def test_partial_usage_flag_resets_between_turns() -> None:
    """A fully measured turn after a partial one reports its own counts."""
    call_count = {"count": 0}

    async def mock_astream(
        messages: list, *, config: dict | None = None
    ) -> AsyncIterator[AIMessageChunk]:
        call_count["count"] += 1
        if call_count["count"] == 1:
            yield AIMessageChunk(content="A")
        else:
            yield AIMessageChunk(content="B", usage_metadata=_usage(100, 10))

    with patch("src.agent.service._build_chat_llm") as mock_build:
        mock_instance = GenericFakeChatModel(messages=iter([]))
        object.__setattr__(mock_instance, "bind_tools", lambda tools: mock_instance)
        object.__setattr__(mock_instance, "astream", mock_astream)
        mock_build.return_value = mock_instance
        agent = Agent()

        async for _ in agent.astream([{"role": "user", "content": "hi"}]):
            pass
        assert agent.get_last_usage() is None

        async for _ in agent.astream([{"role": "user", "content": "again"}]):
            pass
        assert agent.get_last_usage() == {
            "prompt_tokens": 100,
            "uncached_input_tokens": 100,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "completion_tokens": 10,
            "total_tokens": 110,
        }


@pytest.mark.asyncio
async def test_usage_resets_between_turns() -> None:
    """A turn without usage must not inherit the previous turn's counts."""
    call_count = {"count": 0}

    async def mock_astream(
        messages: list, *, config: dict | None = None
    ) -> AsyncIterator[AIMessageChunk]:
        call_count["count"] += 1
        if call_count["count"] == 1:
            yield AIMessageChunk(content="A", usage_metadata=_usage(100, 10))
        else:
            yield AIMessageChunk(content="B")

    with patch("src.agent.service._build_chat_llm") as mock_build:
        mock_instance = GenericFakeChatModel(messages=iter([]))
        object.__setattr__(mock_instance, "bind_tools", lambda tools: mock_instance)
        object.__setattr__(mock_instance, "astream", mock_astream)
        mock_build.return_value = mock_instance
        agent = Agent()

        async for _ in agent.astream([{"role": "user", "content": "hi"}]):
            pass
        assert agent.get_last_usage() is not None

        async for _ in agent.astream([{"role": "user", "content": "again"}]):
            pass
        assert agent.get_last_usage() is None


def test_chat_llm_requests_usage_on_the_stream() -> None:
    """langchain_litellm only defaults include_usage on for OpenAI models."""
    from src.agent.service import _build_chat_llm

    llm = _build_chat_llm(model="anthropic/claude-sonnet-4-6")
    assert getattr(llm, "stream_options") == {"include_usage": True}


class TestUsagePartitioning:
    """`prompt_tokens` is inclusive of the cache counts; the split must be additive.

    Numbers below are from a real Langfuse trace of a cached NGos turn:
    call 1 = 8,764 in / 37 out with 6,799 written to cache;
    call 2 = 8,877 in / 21 out with the same 6,799 read back.
    """

    CALL_1 = _usage(8764, 37, write=6799)
    CALL_2 = _usage(8877, 21, read=6799)

    def _turn(self) -> dict:
        from src.agent.service import _add_turn_usage, _merge_call_usage

        total = _add_turn_usage(None, _merge_call_usage(None, self.CALL_1))
        turn = _add_turn_usage(total, _merge_call_usage(None, self.CALL_2))
        assert turn is not None
        return turn

    def test_components_sum_to_prompt_tokens(self) -> None:
        from src.agent.service import _partition_input_tokens

        usage = _partition_input_tokens(self._turn())
        assert (
            usage["uncached_input_tokens"]
            + usage["cache_read_input_tokens"]
            + usage["cache_creation_input_tokens"]
            == usage["prompt_tokens"]
        )

    def test_matches_the_observed_trace(self) -> None:
        from src.agent.service import _partition_input_tokens

        assert _partition_input_tokens(self._turn()) == {
            "prompt_tokens": 8764 + 8877,
            "uncached_input_tokens": (8764 - 6799) + (8877 - 6799),
            "cache_read_input_tokens": 6799,
            "cache_creation_input_tokens": 6799,
            "completion_tokens": 58,
            "total_tokens": 8764 + 8877 + 58,
        }

    def test_reconstructs_the_billed_cost(self) -> None:
        """The partition must price out to what Langfuse charged for the turn."""
        from src.agent.service import _partition_input_tokens

        usage = _partition_input_tokens(self._turn())
        rate_in, rate_out = 3e-6, 15e-6
        cost = (
            usage["uncached_input_tokens"] * rate_in
            + usage["cache_read_input_tokens"] * rate_in * 0.1
            + usage["cache_creation_input_tokens"] * rate_in * 1.25
            + usage["completion_tokens"] * rate_out
        )
        assert cost == pytest.approx(0.031946 + 0.008589, abs=1e-5)

    def test_naive_pricing_overcharges(self) -> None:
        """Guards the reason uncached_input_tokens exists at all."""
        from src.agent.service import _partition_input_tokens

        usage = _partition_input_tokens(self._turn())
        naive = usage["prompt_tokens"] * 3e-6  # cache tokens billed at full rate
        correct = (
            usage["uncached_input_tokens"] * 3e-6
            + usage["cache_read_input_tokens"] * 3e-7
            + usage["cache_creation_input_tokens"] * 3.75e-6
        )
        # Naive pricing overcharges this turn by ~33%.
        assert naive > correct * 1.3

    def test_remainder_clamped_when_counts_are_not_inclusive(self) -> None:
        """A provider reporting cache counts outside prompt_tokens must not go negative."""
        from src.agent.service import _partition_input_tokens

        usage = _partition_input_tokens(
            {
                "prompt_tokens": 100,
                "completion_tokens": 5,
                "cache_read_input_tokens": 900,
                "cache_creation_input_tokens": 0,
            }
        )
        assert usage["uncached_input_tokens"] == 0
