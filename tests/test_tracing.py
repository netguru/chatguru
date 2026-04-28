"""Unit tests for src/tracing.py — Langfuse singleton helpers."""

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reset_tracing_module() -> None:
    """Reset the module-level _langfuse_initialized flag to False."""
    import tracing

    tracing._langfuse_initialized = False  # noqa: SLF001


# ---------------------------------------------------------------------------
# init_langfuse()
# ---------------------------------------------------------------------------


class TestInitLangfuse:
    def setup_method(self) -> None:
        _reset_tracing_module()

    def teardown_method(self) -> None:
        _reset_tracing_module()

    def test_returns_false_when_disabled(self) -> None:
        """init_langfuse returns False when LANGFUSE_ENABLED is false."""
        mock_settings = MagicMock()
        mock_settings.enabled = False

        with patch("tracing.get_langfuse_settings", return_value=mock_settings):
            from tracing import init_langfuse

            result = init_langfuse()

        assert result is False

    def test_returns_false_when_keys_missing(self) -> None:
        """init_langfuse returns False when public_key or secret_key is absent."""
        mock_settings = MagicMock()
        mock_settings.enabled = True
        mock_settings.public_key = ""
        mock_settings.secret_key = ""

        with patch("tracing.get_langfuse_settings", return_value=mock_settings):
            from tracing import init_langfuse

            result = init_langfuse()

        assert result is False

    def test_returns_true_and_sets_flag_when_configured(self) -> None:
        """init_langfuse initialises the client and sets _langfuse_initialized."""
        mock_settings = MagicMock()
        mock_settings.enabled = True
        mock_settings.public_key = "pk-test"
        mock_settings.secret_key = "sk-test"
        mock_settings.host = "https://cloud.langfuse.com"

        with (
            patch("tracing.get_langfuse_settings", return_value=mock_settings),
            patch("tracing.Langfuse") as mock_langfuse,
        ):
            from tracing import init_langfuse

            result = init_langfuse()

        assert result is True
        mock_langfuse.assert_called_once_with(
            public_key="pk-test",
            secret_key="sk-test",
            host="https://cloud.langfuse.com",
        )

    def test_idempotent_second_call_skips_constructor(self) -> None:
        """Subsequent init_langfuse() calls are no-ops; Langfuse() not called again."""
        mock_settings = MagicMock()
        mock_settings.enabled = True
        mock_settings.public_key = "pk"
        mock_settings.secret_key = "sk"
        mock_settings.host = "https://cloud.langfuse.com"

        with (
            patch("tracing.get_langfuse_settings", return_value=mock_settings),
            patch("tracing.Langfuse") as mock_langfuse,
        ):
            from tracing import init_langfuse

            init_langfuse()
            init_langfuse()

        mock_langfuse.assert_called_once()

    def test_returns_false_when_constructor_raises(self) -> None:
        """init_langfuse catches Langfuse() exceptions and returns False."""
        mock_settings = MagicMock()
        mock_settings.enabled = True
        mock_settings.public_key = "pk"
        mock_settings.secret_key = "sk"
        mock_settings.host = "https://cloud.langfuse.com"

        with (
            patch("tracing.get_langfuse_settings", return_value=mock_settings),
            patch("tracing.Langfuse", side_effect=RuntimeError("connection refused")),
        ):
            from tracing import init_langfuse

            result = init_langfuse()

        assert result is False

    def test_flag_remains_false_after_constructor_exception(self) -> None:
        """A failed init_langfuse() leaves _langfuse_initialized as False."""
        import tracing

        mock_settings = MagicMock()
        mock_settings.enabled = True
        mock_settings.public_key = "pk"
        mock_settings.secret_key = "sk"
        mock_settings.host = "https://cloud.langfuse.com"

        with (
            patch("tracing.get_langfuse_settings", return_value=mock_settings),
            patch("tracing.Langfuse", side_effect=RuntimeError("boom")),
        ):
            tracing.init_langfuse()

        assert tracing._langfuse_initialized is False  # noqa: SLF001


# ---------------------------------------------------------------------------
# is_langfuse_initialized()
# ---------------------------------------------------------------------------


class TestIsLangfuseInitialized:
    def setup_method(self) -> None:
        _reset_tracing_module()

    def teardown_method(self) -> None:
        _reset_tracing_module()

    def test_false_before_init(self) -> None:
        from tracing import is_langfuse_initialized

        assert is_langfuse_initialized() is False

    def test_true_after_successful_init(self) -> None:
        mock_settings = MagicMock()
        mock_settings.enabled = True
        mock_settings.public_key = "pk"
        mock_settings.secret_key = "sk"
        mock_settings.host = "https://cloud.langfuse.com"

        with (
            patch("tracing.get_langfuse_settings", return_value=mock_settings),
            patch("tracing.Langfuse"),
        ):
            from tracing import init_langfuse, is_langfuse_initialized

            init_langfuse()

        assert is_langfuse_initialized() is True


# ---------------------------------------------------------------------------
# get_langfuse_handler()
# ---------------------------------------------------------------------------


class TestGetLangfuseHandler:
    def setup_method(self) -> None:
        _reset_tracing_module()

    def teardown_method(self) -> None:
        _reset_tracing_module()

    def test_returns_none_when_not_initialized(self) -> None:
        from tracing import get_langfuse_handler

        assert get_langfuse_handler() is None

    def test_returns_handler_when_initialized(self) -> None:
        import tracing

        tracing._langfuse_initialized = True  # noqa: SLF001
        mock_handler = MagicMock()

        with patch("tracing.LangfuseCallbackHandler", return_value=mock_handler):
            result = tracing.get_langfuse_handler()

        assert result is mock_handler


# ---------------------------------------------------------------------------
# flush_langfuse()
# ---------------------------------------------------------------------------


class TestFlushLangfuse:
    def setup_method(self) -> None:
        _reset_tracing_module()

    def teardown_method(self) -> None:
        _reset_tracing_module()

    def test_no_op_when_not_initialized(self) -> None:
        """flush_langfuse does nothing and does not raise when Langfuse is off."""
        with patch("tracing.get_client") as mock_get_client:
            from tracing import flush_langfuse

            flush_langfuse()

        mock_get_client.assert_not_called()

    def test_calls_flush_when_initialized(self) -> None:
        import tracing

        tracing._langfuse_initialized = True  # noqa: SLF001
        mock_client = MagicMock()

        with patch("tracing.get_client", return_value=mock_client):
            tracing.flush_langfuse()

        mock_client.flush.assert_called_once()

    def test_swallows_flush_exception(self) -> None:
        """flush_langfuse catches exceptions from get_client().flush() without raising."""
        import tracing

        tracing._langfuse_initialized = True  # noqa: SLF001
        mock_client = MagicMock()
        mock_client.flush.side_effect = RuntimeError("network error")

        with patch("tracing.get_client", return_value=mock_client):
            tracing.flush_langfuse()  # must not raise


# ---------------------------------------------------------------------------
# Concurrency: init_langfuse() is idempotent under concurrent callers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_init_langfuse_idempotent_under_concurrent_callers() -> None:
    """Concurrent init_langfuse() calls initialise Langfuse exactly once."""
    import asyncio

    import tracing

    tracing._langfuse_initialized = False  # noqa: SLF001

    mock_settings = MagicMock()
    mock_settings.enabled = True
    mock_settings.public_key = "pk"
    mock_settings.secret_key = "sk"
    mock_settings.host = "https://cloud.langfuse.com"

    call_count = {"n": 0}
    original_langfuse = tracing.Langfuse

    class CountingLangfuse:
        def __init__(self, **_kwargs: object) -> None:
            call_count["n"] += 1

    try:
        with patch("tracing.get_langfuse_settings", return_value=mock_settings):
            tracing.Langfuse = CountingLangfuse  # noqa: PGH003
            results = await asyncio.gather(
                asyncio.to_thread(tracing.init_langfuse),
                asyncio.to_thread(tracing.init_langfuse),
                asyncio.to_thread(tracing.init_langfuse),
            )
    finally:
        tracing.Langfuse = original_langfuse  # noqa: PGH003
        tracing._langfuse_initialized = False  # noqa: SLF001

    # All callers should report True once initialized
    assert all(results)
    # Langfuse() constructor must have been called at most once
    assert call_count["n"] <= 1
