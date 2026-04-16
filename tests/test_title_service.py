"""Tests for title generation adapters and fallback behavior."""

from unittest.mock import AsyncMock, MagicMock

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
