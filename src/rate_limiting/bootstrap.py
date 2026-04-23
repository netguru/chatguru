"""Process-wide Redis rate limiter (FastAPI app lifespan)."""

import redis.asyncio as aioredis

from config import get_logger, get_rate_limit_settings

logger = get_logger(__name__)

_redis_client: aioredis.Redis | None = None

# Atomic Lua script: check the current count, reject if at or above the limit,
# otherwise increment and set TTL on first use.
#
# All three operations (GET / INCR / EXPIRE) run inside a single Redis
# transaction — there is no window between the check and the increment where a
# concurrent request can slip through and exceed the quota.
#
# Returns:
#   1  — request is within the limit (counter has been incremented).
#   0  — limit already reached (counter unchanged).
_LUA_CONSUME = """
local count = redis.call('GET', KEYS[1])
count = count and tonumber(count) or 0
if count >= tonumber(ARGV[2]) then
    return 0
end
local new_count = redis.call('INCR', KEYS[1])
if new_count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return 1
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
        logger.info(
            "Rate limiting is disabled (RATE_LIMIT_ENABLED is false or not set)"
        )
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


async def consume_rate_limit(ip: str) -> bool:
    """Atomically check and consume one rate-limit slot for ``ip``.

    Uses a single Lua script so the check and increment are one atomic Redis
    operation — concurrent requests from the same IP cannot both slip through
    the guard before either has recorded its use (TOCTOU-safe).

    The slot is consumed *before* the AI call begins, so a request that starts
    streaming but fails mid-way still counts against the quota. This prevents
    clients from exploiting streaming errors to bypass the limit.

    When rate limiting is disabled (no Redis client) every request is allowed.

    Args:
        ip: Client IP address used as the rate limit key.

    Returns:
        True  — slot consumed; request is allowed.
        False — limit already reached; caller should send a rate_limit_exceeded error.
    """
    client = _get_redis_client()
    if client is None:
        return True

    settings = get_rate_limit_settings()
    key = f"rate_limit:chat:{ip}"
    result = await client.eval(  # type: ignore[misc]
        _LUA_CONSUME, 1, key, str(settings.window_seconds), str(settings.max_messages)
    )
    allowed = bool(result)
    if not allowed:
        logger.info(
            "Rate limit exceeded for ip=%s (limit=%d per %ds)",
            ip,
            settings.max_messages,
            settings.window_seconds,
        )
    return allowed
