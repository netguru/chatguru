"""Tests for the Redis-backed rate limiting module."""

import asyncio
import os
from collections.abc import AsyncIterator, Callable, Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from rate_limiting.bootstrap import (
    _LUA_CONSUME,
    _get_redis_client,
    consume_rate_limit,
    init_rate_limiting,
    is_rate_limiting_enabled,
    shutdown_rate_limiting,
)


# ---------------------------------------------------------------------------
# Module-level fixture: disable real Redis during all integration tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _disable_real_redis_in_lifespan() -> Iterator[None]:
    """Ensure the app lifespan never tries to open a real Redis connection.

    The integration tests patch ``consume_rate_limit`` directly on the route
    module, so we only need the lifecycle hooks to be no-ops.
    """
    with (
        patch("api.main.init_rate_limiting", new=AsyncMock()),
        patch("api.main.shutdown_rate_limiting", new=AsyncMock()),
    ):
        yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_redis_mock(stored_value: str | None = None) -> AsyncMock:
    """Return an AsyncMock that behaves like an aioredis.Redis client.

    ``stored_value`` is what ``GET`` would return for any key, used to
    simulate the counter already being set.
    """
    client = AsyncMock()
    client.ping = AsyncMock(return_value=True)
    client.get = AsyncMock(return_value=stored_value)
    # eval returns 1 (allowed) by default; individual tests override this.
    client.eval = AsyncMock(return_value=1)
    client.aclose = AsyncMock()
    return client


# ---------------------------------------------------------------------------
# is_rate_limiting_enabled
# ---------------------------------------------------------------------------


def test_rate_limiting_disabled_by_default() -> None:
    with patch("rate_limiting.bootstrap.get_rate_limit_settings") as mock_settings:
        mock_settings.return_value = MagicMock(enabled=False)
        assert is_rate_limiting_enabled() is False


def test_rate_limiting_enabled_when_configured() -> None:
    with patch("rate_limiting.bootstrap.get_rate_limit_settings") as mock_settings:
        mock_settings.return_value = MagicMock(enabled=True)
        assert is_rate_limiting_enabled() is True


# ---------------------------------------------------------------------------
# init / shutdown lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_init_rate_limiting_skipped_when_disabled() -> None:
    with (
        patch("rate_limiting.bootstrap.get_rate_limit_settings") as mock_settings,
        patch("rate_limiting.bootstrap._redis_client", None),
    ):
        mock_settings.return_value = MagicMock(enabled=False)
        await init_rate_limiting()
        assert _get_redis_client() is None


@pytest.mark.asyncio
async def test_init_rate_limiting_connects_to_redis() -> None:
    mock_client = _make_redis_mock()

    with (
        patch("rate_limiting.bootstrap.get_rate_limit_settings") as mock_settings,
        patch("rate_limiting.bootstrap.aioredis.from_url", return_value=mock_client),
        patch("rate_limiting.bootstrap._redis_client", None),
    ):
        mock_settings.return_value = MagicMock(
            enabled=True,
            redis_url="redis://localhost:6379/0",
            max_messages=10,
            window_seconds=86400,
        )
        import rate_limiting.bootstrap as bootstrap_mod

        bootstrap_mod._redis_client = None
        await init_rate_limiting()
        mock_client.ping.assert_called_once()
        bootstrap_mod._redis_client = None  # cleanup


@pytest.mark.asyncio
async def test_shutdown_closes_client() -> None:
    import rate_limiting.bootstrap as bootstrap_mod

    mock_client = _make_redis_mock()
    bootstrap_mod._redis_client = mock_client
    await shutdown_rate_limiting()
    mock_client.aclose.assert_called_once()
    assert bootstrap_mod._redis_client is None


# ---------------------------------------------------------------------------
# consume_rate_limit — unit tests (mocked Redis)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consume_rate_limit_allowed_when_no_client() -> None:
    """When rate limiting is disabled (no Redis client) every request passes."""
    import rate_limiting.bootstrap as bootstrap_mod

    original = bootstrap_mod._redis_client
    bootstrap_mod._redis_client = None
    try:
        assert await consume_rate_limit("1.2.3.4") is True
    finally:
        bootstrap_mod._redis_client = original


@pytest.mark.asyncio
async def test_consume_rate_limit_allowed_within_quota() -> None:
    """Lua script returns 1 → request is allowed and True is returned."""
    import rate_limiting.bootstrap as bootstrap_mod

    mock_client = _make_redis_mock()
    mock_client.eval = AsyncMock(return_value=1)

    with patch("rate_limiting.bootstrap.get_rate_limit_settings") as mock_settings:
        mock_settings.return_value = MagicMock(max_messages=5, window_seconds=86400)
        original = bootstrap_mod._redis_client
        bootstrap_mod._redis_client = mock_client
        try:
            result = await consume_rate_limit("1.2.3.4")
        finally:
            bootstrap_mod._redis_client = original

    assert result is True
    mock_client.eval.assert_called_once_with(
        _LUA_CONSUME, 1, "rate_limit:chat:1.2.3.4", "86400", "5"
    )


@pytest.mark.asyncio
async def test_consume_rate_limit_blocked_at_quota() -> None:
    """Lua script returns 0 → request is blocked and False is returned."""
    import rate_limiting.bootstrap as bootstrap_mod

    mock_client = _make_redis_mock()
    mock_client.eval = AsyncMock(return_value=0)

    with patch("rate_limiting.bootstrap.get_rate_limit_settings") as mock_settings:
        mock_settings.return_value = MagicMock(max_messages=5, window_seconds=86400)
        original = bootstrap_mod._redis_client
        bootstrap_mod._redis_client = mock_client
        try:
            result = await consume_rate_limit("1.2.3.4")
        finally:
            bootstrap_mod._redis_client = original

    assert result is False


@pytest.mark.asyncio
async def test_consume_rate_limit_uses_ip_as_key() -> None:
    """The Redis key must include the caller's IP address."""
    import rate_limiting.bootstrap as bootstrap_mod

    mock_client = _make_redis_mock()
    mock_client.eval = AsyncMock(return_value=1)

    with patch("rate_limiting.bootstrap.get_rate_limit_settings") as mock_settings:
        mock_settings.return_value = MagicMock(max_messages=3, window_seconds=3600)
        original = bootstrap_mod._redis_client
        bootstrap_mod._redis_client = mock_client
        try:
            await consume_rate_limit("10.0.0.1")
        finally:
            bootstrap_mod._redis_client = original

    call_args = mock_client.eval.call_args
    assert call_args[0][2] == "rate_limit:chat:10.0.0.1"


# ---------------------------------------------------------------------------
# Atomicity guarantee — Lua script logic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_requests_cannot_both_exceed_limit() -> None:
    """Simulate the TOCTOU scenario: two concurrent callers should not both
    receive 'allowed' once the quota is exhausted.

    We model the Lua script as a real atomic counter in-process so the test
    exercises the before/after boundary rather than just the mock.
    """
    import rate_limiting.bootstrap as bootstrap_mod

    counter = {"value": 0}
    max_messages = 1

    def atomic_eval(
        script: str, num_keys: int, key: str, window: str, limit: str
    ) -> int:
        """Simulate the Lua script atomically (no async gap between check and incr)."""
        if counter["value"] >= int(limit):
            return 0
        counter["value"] += 1
        return 1

    mock_client = AsyncMock()
    mock_client.eval = AsyncMock(side_effect=atomic_eval)

    with patch("rate_limiting.bootstrap.get_rate_limit_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            max_messages=max_messages, window_seconds=86400
        )
        original = bootstrap_mod._redis_client
        bootstrap_mod._redis_client = mock_client
        try:
            results = await asyncio.gather(
                consume_rate_limit("1.2.3.4"),
                consume_rate_limit("1.2.3.4"),
                consume_rate_limit("1.2.3.4"),
            )
        finally:
            bootstrap_mod._redis_client = original

    allowed = sum(1 for r in results if r is True)
    blocked = sum(1 for r in results if r is False)
    assert (
        allowed == max_messages
    ), f"Expected exactly {max_messages} allowed, got {allowed}"
    assert blocked == 2, f"Expected 2 blocked, got {blocked}"


# ---------------------------------------------------------------------------
# _get_client_ip — unit tests
# ---------------------------------------------------------------------------


def test_get_client_ip_returns_direct_connection_ip() -> None:
    from api.routes.chat import _get_client_ip

    mock_ws = MagicMock()
    mock_ws.client = MagicMock(host="192.168.1.1")
    mock_ws.headers = {}

    with patch("api.routes.chat.get_rate_limit_settings") as mock_settings:
        mock_settings.return_value = MagicMock(trust_proxy=False)
        assert _get_client_ip(mock_ws) == "192.168.1.1"


def test_get_client_ip_returns_none_when_client_is_none() -> None:
    from api.routes.chat import _get_client_ip

    mock_ws = MagicMock()
    mock_ws.client = None
    mock_ws.headers = {}

    with patch("api.routes.chat.get_rate_limit_settings") as mock_settings:
        mock_settings.return_value = MagicMock(trust_proxy=False)
        assert _get_client_ip(mock_ws) is None


def test_get_client_ip_reads_x_forwarded_for_when_trust_proxy_enabled() -> None:
    from api.routes.chat import _get_client_ip

    mock_ws = MagicMock()
    mock_ws.client = MagicMock(host="10.0.0.1")
    mock_ws.headers = {"x-forwarded-for": "203.0.113.5, 10.0.0.1"}

    with patch("api.routes.chat.get_rate_limit_settings") as mock_settings:
        mock_settings.return_value = MagicMock(trust_proxy=True)
        assert _get_client_ip(mock_ws) == "203.0.113.5"


def test_get_client_ip_reads_x_real_ip_when_no_forwarded_for() -> None:
    from api.routes.chat import _get_client_ip

    mock_ws = MagicMock()
    mock_ws.client = MagicMock(host="10.0.0.1")
    mock_ws.headers = {"x-real-ip": "203.0.113.99"}

    with patch("api.routes.chat.get_rate_limit_settings") as mock_settings:
        mock_settings.return_value = MagicMock(trust_proxy=True)
        assert _get_client_ip(mock_ws) == "203.0.113.99"


def test_get_client_ip_ignores_proxy_headers_when_trust_proxy_disabled() -> None:
    from api.routes.chat import _get_client_ip

    mock_ws = MagicMock()
    mock_ws.client = MagicMock(host="10.0.0.1")
    mock_ws.headers = {"x-forwarded-for": "203.0.113.5", "x-real-ip": "203.0.113.99"}

    with patch("api.routes.chat.get_rate_limit_settings") as mock_settings:
        mock_settings.return_value = MagicMock(trust_proxy=False)
        assert _get_client_ip(mock_ws) == "10.0.0.1"


# ---------------------------------------------------------------------------
# WebSocket integration — rate limit exceeded path
# ---------------------------------------------------------------------------


def _mock_astream_chunks(chunks: list[str]) -> Callable[..., AsyncIterator[str]]:
    async def _gen(
        messages: list[dict[str, str]],
        *,
        session_id: str | None = None,
        visitor_id: str | None = None,
    ) -> AsyncIterator[str]:
        for chunk in chunks:
            yield chunk

    return _gen


def test_websocket_rate_limit_exceeded_sends_error(async_app: TestClient) -> None:
    """When consume_rate_limit returns False the endpoint sends a rate_limit_exceeded error."""
    with (
        patch("api.routes.chat.Agent") as mock_agent_class,
        patch("api.routes.chat.consume_rate_limit", new=AsyncMock(return_value=False)),
    ):
        mock_agent_class.return_value = MagicMock(
            astream=_mock_astream_chunks(["Hello"])
        )

        with async_app.websocket_connect("/ws") as ws:
            ws.send_json(
                {
                    "visitor_id": "visitor-rate-limited",
                    "session_id": "sess-rl",
                    "messages": [{"role": "user", "content": "hi"}],
                }
            )
            data = ws.receive_json()

    assert data["type"] == "error"
    assert data["session_id"] == "sess-rl"
    assert "limit" in data["content"].lower() or "rate" in data["content"].lower()


def test_websocket_rate_limit_allowed_continues_to_stream(
    async_app: TestClient,
) -> None:
    """When consume_rate_limit returns True the full streaming response is delivered."""
    chunks = ["Hello ", "world!"]
    with (
        patch("api.routes.chat.Agent") as mock_agent_class,
        patch("api.routes.chat.consume_rate_limit", new=AsyncMock(return_value=True)),
    ):
        mock_agent_class.return_value = MagicMock(
            astream=_mock_astream_chunks(chunks), last_trace_id=None
        )

        with async_app.websocket_connect("/ws") as ws:
            ws.send_json(
                {
                    "visitor_id": "visitor-rl-ok",
                    "session_id": "sess-ok",
                    "messages": [{"role": "user", "content": "hi"}],
                }
            )

            tokens = []
            while True:
                data = ws.receive_json()
                if data["type"] == "token":
                    tokens.append(data["content"])
                elif data["type"] == "end":
                    break
                elif data["type"] == "error":
                    pytest.fail(f"Unexpected error: {data['content']}")

    assert "".join(tokens) == "".join(chunks)


def test_websocket_rate_limit_skipped_when_ip_unknown(async_app: TestClient) -> None:
    """When the client IP cannot be determined, rate limiting is skipped entirely
    rather than sharing a single 'unknown' bucket across all such connections."""
    chunks = ["Hi!"]
    consume_mock = AsyncMock(return_value=True)

    with (
        patch("api.routes.chat.Agent") as mock_agent_class,
        patch("api.routes.chat.consume_rate_limit", consume_mock),
        patch("api.routes.chat._get_client_ip", return_value=None),
    ):
        mock_agent_class.return_value = MagicMock(
            astream=_mock_astream_chunks(chunks), last_trace_id=None
        )

        with async_app.websocket_connect("/ws") as ws:
            ws.send_json(
                {
                    "visitor_id": "visitor-unknown-ip",
                    "session_id": "sess-unknown",
                    "messages": [{"role": "user", "content": "hi"}],
                }
            )
            while True:
                data = ws.receive_json()
                if data["type"] == "end":
                    break
                elif data["type"] == "error":
                    pytest.fail(f"Unexpected error: {data['content']}")

    consume_mock.assert_not_called()
