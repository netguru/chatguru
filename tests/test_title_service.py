"""Tests for the LLM-based title generation service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.title_service import generate_title, truncate_title


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


# ── generate_title: LLM path ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_title_uses_llm_response() -> None:
    """When LLM succeeds, its response is returned as the title."""
    llm_response = MagicMock()
    llm_response.content = "Return Policy For Online Orders"

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=llm_response)

    with patch("agent.title_service._get_title_llm", return_value=mock_llm):
        result = await generate_title("What is the return policy for online orders?")

    assert result == "Return Policy For Online Orders"


@pytest.mark.asyncio
async def test_generate_title_strips_quotes_from_llm_response() -> None:
    """LLM responses wrapped in quotes are cleaned up."""
    llm_response = MagicMock()
    llm_response.content = '"Shopping Cart Help"'

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=llm_response)

    with patch("agent.title_service._get_title_llm", return_value=mock_llm):
        result = await generate_title("I need help with my cart")

    assert result == "Shopping Cart Help"


@pytest.mark.asyncio
async def test_generate_title_falls_back_on_llm_error() -> None:
    """If the LLM call raises, the function falls back to truncation silently."""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("network error"))

    with patch("agent.title_service._get_title_llm", return_value=mock_llm):
        result = await generate_title("short message")

    assert result == "short message"


@pytest.mark.asyncio
async def test_generate_title_falls_back_on_empty_llm_response() -> None:
    """Empty LLM response triggers the truncation fallback."""
    llm_response = MagicMock()
    llm_response.content = "   "

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=llm_response)

    with patch("agent.title_service._get_title_llm", return_value=mock_llm):
        result = await generate_title("Fallback message here")

    assert result == "Fallback message here"
