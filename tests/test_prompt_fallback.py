"""Unit tests for the local system-prompt fallback resolver.

Covers ``agent.prompt.load_fallback_prompt`` — the ``AGENT_SYSTEM_PROMPT_FALLBACK_FILE``
resolution used when the Langfuse prompt fetch is unavailable.
"""

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agent.prompt import SYSTEM_PROMPT, load_fallback_prompt


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    """Reset the ``lru_cache`` around each case so settings patches take effect."""
    load_fallback_prompt.cache_clear()
    yield
    load_fallback_prompt.cache_clear()


def _settings(path: str) -> SimpleNamespace:
    return SimpleNamespace(system_prompt_fallback_file=path)


def test_unset_returns_builtin() -> None:
    with patch("agent.prompt.get_agent_settings", return_value=_settings("")):
        assert load_fallback_prompt() == SYSTEM_PROMPT


def test_valid_file_returns_contents(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("# Custom prompt\nBe helpful.", encoding="utf-8")
    with patch(
        "agent.prompt.get_agent_settings", return_value=_settings(str(prompt_file))
    ):
        assert load_fallback_prompt() == "# Custom prompt\nBe helpful."


def test_missing_file_falls_back_and_warns(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.md"
    with (
        patch("agent.prompt.get_agent_settings", return_value=_settings(str(missing))),
        patch("agent.prompt.logger") as mock_logger,
    ):
        assert load_fallback_prompt() == SYSTEM_PROMPT
    mock_logger.warning.assert_called_once()
    assert "Could not read" in mock_logger.warning.call_args.args[0]


def test_empty_file_falls_back_and_warns(tmp_path: Path) -> None:
    empty = tmp_path / "empty.md"
    empty.write_text("   \n\t", encoding="utf-8")
    with (
        patch("agent.prompt.get_agent_settings", return_value=_settings(str(empty))),
        patch("agent.prompt.logger") as mock_logger,
    ):
        assert load_fallback_prompt() == SYSTEM_PROMPT
    mock_logger.warning.assert_called_once()
    assert "is empty" in mock_logger.warning.call_args.args[0]


def test_result_is_cached(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("first", encoding="utf-8")
    with patch(
        "agent.prompt.get_agent_settings", return_value=_settings(str(prompt_file))
    ):
        assert load_fallback_prompt() == "first"
        prompt_file.write_text("second", encoding="utf-8")
        # Cached: the file is read at most once per process.
        assert load_fallback_prompt() == "first"
