"""Agent component tests."""

import json
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessageChunk

from src.agent.service import Agent

if TYPE_CHECKING:
    from document_rag.models import DocumentRetrievalHit


class _FakeDocumentRepository:
    async def connect(self) -> None:
        return

    async def search(self, query: str, limit: int = 5) -> list[DocumentRetrievalHit]:
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
    tool = Agent._create_document_rag_tool(_FakeDocumentRepository())
    payload = await tool.ainvoke({"query": "install"})
    data = json.loads(payload)
    assert data["hits"][0]["snippet"] == "Snippet for install"
    assert data["hits"][0]["source"]["source_id"] == "doc-42"
    assert data["hits"][0]["source"]["source_uri"] == "docs/guide.md"


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

        with patch("src.agent.service.get_langfuse_handler", return_value=None):
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

    mock_handler = MagicMock()
    mock_handler.last_trace_id = "trace-first"

    with patch("src.agent.service._build_chat_llm") as mock_build:
        mock_instance = GenericFakeChatModel(messages=iter([]))
        object.__setattr__(mock_instance, "bind_tools", lambda tools: mock_instance)
        object.__setattr__(mock_instance, "astream", mock_astream)
        mock_build.return_value = mock_instance

        with patch("src.agent.service.get_langfuse_handler", return_value=mock_handler):
            agent = Agent()

            # First call gets a trace ID
            async for _ in agent.astream([{"role": "user", "content": "Hello"}]):
                pass
            assert agent.last_trace_id == "trace-first"

            # Between calls the handler is reset — simulate disabled handler on second call
            with patch("src.agent.service.get_langfuse_handler", return_value=None):
                async for _ in agent.astream([{"role": "user", "content": "Hello"}]):
                    pass
                assert agent.last_trace_id is None


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
