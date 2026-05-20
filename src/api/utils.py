"""Shared utilities for API route handlers."""

from starlette.requests import HTTPConnection

from config import get_logger, get_rate_limit_settings

logger = get_logger(__name__)

# ── MIME-type helpers ─────────────────────────────────────────────────────────

# Accepted types for the raw image upload endpoint.
ALLOWED_IMAGE_MIME_TYPES: frozenset[str] = frozenset(
    {"image/png", "image/jpeg", "image/gif", "image/webp"}
)

# Types that are safe to store and later serve with their original Content-Type.
# Anything outside this list is normalised to application/octet-stream so a
# client-supplied type can never trigger in-browser script execution.
_SAFE_STORED_MIME_TYPES: frozenset[str] = frozenset(
    {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/plain",
        "text/markdown",
        *ALLOWED_IMAGE_MIME_TYPES,
    }
)


def safe_mime_type(mime: str | None) -> str:
    """Return *mime* if it is in the safe allowlist, otherwise ``application/octet-stream``.

    Prevents a maliciously crafted Content-Type (e.g. ``text/html``) from
    being persisted and later served inline to other visitors.
    """
    if mime and mime in _SAFE_STORED_MIME_TYPES:
        return mime
    return "application/octet-stream"


def get_client_ip(conn: HTTPConnection) -> str | None:
    """Extract the real client IP address from an HTTP or WebSocket connection.

    Returns ``None`` when the IP cannot be determined (e.g. certain ASGI
    transports set ``conn.client`` to ``None``). Callers must skip rate
    limiting for a ``None`` result rather than falling back to a shared key —
    a single shared key would let any one client exhaust the quota for every
    other client whose IP is unknown.

    When ``RATE_LIMIT_TRUST_PROXY`` is True, the ``X-Forwarded-For`` and
    ``X-Real-IP`` headers are checked first.  Only enable proxy trust when
    the application is behind a known, trusted reverse proxy — never in
    direct-to-internet deployments, as headers can be spoofed by clients.
    """
    if get_rate_limit_settings().trust_proxy:
        forwarded_for = conn.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        real_ip = conn.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
    client = conn.client
    if client is None:
        logger.info(
            "Cannot determine client IP — rate limiting skipped for this connection"
        )
        return None
    return client.host
