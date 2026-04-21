"""Process-wide Redis rate limiter (FastAPI app lifespan)."""

import redis.asyncio as aioredis

from config import get_logger, get_rate_limit_settings

logger = get_logger(__name__)

_redis_client: aioredis.Redis | None = None

# Atomic Lua script: increment a counter, set TTL on the first increment.
# Returns the counter value after incrementing.
# Using Lua guarantees the INCR + EXPIRE pair is atomic — no risk of a key
# with a counter > 0 but no TTL if the process dies between the two calls.
_LUA_INCREMENT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


def is_rate_limiting_enabled() -> bool:
    """Return True when RATE_LIMIT_ENABLED is configured and true."""
    return bool(get_rate_limit_settings().enabled)


async def init_rate_limiting() -> None:
    """Initialize the process-wide Redis client (call once at startup).

    When ``RATE_LIMIT_ENABLED`` is false this is a no-op — rate limiting
    remains disabled and all requests are allowed through.
    """
    global _redis_client  # noqa: PLW0603
    if not is_rate_limiting_enabled():
        logger.info("Rate limiting is disabled (RATE_LIMIT_ENABLED not set)")
        return
    if _redis_client is not None:
        return
    settings = get_rate_limit_settings()
    client: aioredis.Redis = aioredis.from_url(
        settings.redis_url, decode_responses=True
    )
    await client.ping()  # type: ignore[misc]
    _redis_client = client
    logger.info(
        "Rate limiting initialized (limit=%d per %ds, redis=%s)",
        settings.max_messages,
        settings.window_seconds,
        settings.redis_url,
    )


async def shutdown_rate_limiting() -> None:
    """Close the Redis connection (call at shutdown)."""
    global _redis_client  # noqa: PLW0603
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Rate limiting shut down")


def _get_redis_client() -> aioredis.Redis | None:
    return _redis_client


async def check_rate_limit(ip: str) -> bool:
    """Return True if the IP is within the allowed rate, False if it should be blocked.

    Read-only — does not increment the counter. Call :func:`record_ai_response`
    after a successful AI reply to consume one slot.

    When rate limiting is disabled (no Redis client) every request is allowed.

    Args:
        ip: Client IP address used as the rate limit key.

    Returns:
        True  — request is allowed.
        False — limit reached; caller should send a rate_limit_exceeded error.
    """
    client = _get_redis_client()
    if client is None:
        return True

    settings = get_rate_limit_settings()
    key = f"rate_limit:chat:{ip}"
    raw = await client.get(key)
    count = int(raw) if raw is not None else 0
    allowed = count < settings.max_messages
    if not allowed:
        logger.info(
            "Rate limit exceeded for ip=%s (count=%d, limit=%d)",
            ip,
            count,
            settings.max_messages,
        )
    return bool(allowed)


async def record_ai_response(ip: str) -> None:
    """Increment the rate limit counter after a successful AI response.

    Must be called once per completed AI reply. Skipped when rate limiting
    is disabled. Uses the same atomic Lua script to set the TTL on first use.

    Args:
        ip: Client IP address used as the rate limit key.
    """
    client = _get_redis_client()
    if client is None:
        return

    settings = get_rate_limit_settings()
    key = f"rate_limit:chat:{ip}"
    await client.eval(_LUA_INCREMENT, 1, key, str(settings.window_seconds))  # type: ignore[misc]
    logger.debug("Recorded AI response for ip=%s", ip)
