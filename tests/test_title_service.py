"""Tests for title generation adapters and fallback behavior."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from config import LLMSettings
from title_generation.adapters.openai import OpenAITitleGenerator
from title_generation.utils import truncate_title


# ── truncate_title unit tests ──────────────────────────────────────────────


def test_truncate_short_message_unchanged() -> None:
    assert truncate_title("Hello!") == "Hello!"


def test_truncate_exactly_at_limit() -> None:
    msg = "x" * 60
    assert truncate_title(msg) == msg


def test_truncate_breaks_at_word_boundary() -> None:
    # 67 chars: forces truncation at word boundary before position 60
    msg = "one two three four five six seven eight nine ten eleven twelve"
    result = truncate_title(msg)
    assert result.endswith("…")
    assert len(result) <= 61  # 60 chars + ellipsis char
    assert not result[:-1].endswith(" ")


def test_truncate_no_space_falls_back_to_hard_cut() -> None:
    msg = "a" * 80
    result = truncate_title(msg)
    assert result == "a" * 60 + "…"


def test_truncate_strips_whitespace() -> None:
    assert truncate_title("  hello  ") == "hello"


# ── OpenAI adapter path ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_openai_generator_uses_llm_response() -> None:
    """When LLM succeeds, its response is returned as the title."""
    llm_response = MagicMock()
    llm_response.content = "Return Policy For Online Orders"

    generator = OpenAITitleGenerator(LLMSettings())
    generator._llm = MagicMock()
    generator._llm.ainvoke = AsyncMock(return_value=llm_response)

    result = await generator.generate("What is the return policy for online orders?")

    assert result == "Return Policy For Online Orders"


@pytest.mark.asyncio
async def test_openai_generator_strips_quotes_from_llm_response() -> None:
    """LLM responses wrapped in quotes are cleaned up."""
    llm_response = MagicMock()
    llm_response.content = '"Shopping Cart Help"'

    generator = OpenAITitleGenerator(LLMSettings())
    generator._llm = MagicMock()
    generator._llm.ainvoke = AsyncMock(return_value=llm_response)

    result = await generator.generate("I need help with my cart")

    assert result == "Shopping Cart Help"


@pytest.mark.asyncio
async def test_openai_generator_falls_back_on_llm_error() -> None:
    """If the LLM call raises, the function falls back to truncation silently."""
    generator = OpenAITitleGenerator(LLMSettings())
    generator._llm = MagicMock()
    generator._llm.ainvoke = AsyncMock(side_effect=RuntimeError("network error"))

    result = await generator.generate("short message")

    assert result == "short message"


@pytest.mark.asyncio
async def test_openai_generator_falls_back_on_empty_llm_response() -> None:
    """Empty LLM response triggers the truncation fallback."""
    llm_response = MagicMock()
    llm_response.content = "   "

    generator = OpenAITitleGenerator(LLMSettings())
    generator._llm = MagicMock()
    generator._llm.ainvoke = AsyncMock(return_value=llm_response)

    result = await generator.generate("Fallback message here")

    assert result == "Fallback message here"


@pytest.mark.asyncio
async def test_openai_generator_attaches_langfuse_callback_when_initialized() -> None:
    """When Langfuse is initialized, its callback handler is passed to ainvoke."""
    llm_response = MagicMock()
    llm_response.content = "Title From LLM"

    mock_handler = MagicMock()

    generator = OpenAITitleGenerator(LLMSettings())
    generator._llm = MagicMock()
    generator._llm.ainvoke = AsyncMock(return_value=llm_response)

    with patch(
        "title_generation.adapters.openai.get_langfuse_handler",
        return_value=mock_handler,
    ):
        result = await generator.generate("Some question")

    assert result == "Title From LLM"
    _, call_kwargs = generator._llm.ainvoke.call_args
    assert call_kwargs.get("config", {}).get("callbacks") == [mock_handler]


@pytest.mark.asyncio
async def test_openai_generator_no_langfuse_callback_when_not_initialized() -> None:
    """When Langfuse is not initialized, ainvoke is called without callbacks."""
    llm_response = MagicMock()
    llm_response.content = "Another Title"

    generator = OpenAITitleGenerator(LLMSettings())
    generator._llm = MagicMock()
    generator._llm.ainvoke = AsyncMock(return_value=llm_response)

    with patch(
        "title_generation.adapters.openai.get_langfuse_handler", return_value=None
    ):
        result = await generator.generate("Another question")

    assert result == "Another Title"
    _, call_kwargs = generator._llm.ainvoke.call_args
    assert not call_kwargs.get("config", {}).get("callbacks")
