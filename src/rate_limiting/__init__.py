"""
Rate limiting package: Redis-backed per-IP message rate limiter.

Import lifecycle helpers from the package root (re-exported from :mod:`rate_limiting.bootstrap`).
"""

from rate_limiting.bootstrap import (
    check_rate_limit,
    init_rate_limiting,
    is_rate_limiting_enabled,
    record_ai_response,
    shutdown_rate_limiting,
)

__all__ = [
    "check_rate_limit",
    "init_rate_limiting",
    "is_rate_limiting_enabled",
    "record_ai_response",
    "shutdown_rate_limiting",
]
