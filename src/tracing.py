"""Shared Langfuse tracing helpers used across services (agent, title generation, etc.)."""

import asyncio
import threading

from langfuse import (
    Langfuse,
    get_client,
    propagate_attributes,
)

# (get_client re-exported)
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler

from config import get_langfuse_settings, get_logger

logger = get_logger("tracing")

_langfuse_initialized = False
_init_lock = threading.Lock()


def init_langfuse() -> bool:
    """
    Initialize Langfuse client if enabled and configured.

    Uses the singleton pattern — the Langfuse client is initialised once per
    process.  Safe to call multiple times; subsequent calls are no-ops.

    Returns:
        True if Langfuse was successfully initialised, False otherwise.
    """
    global _langfuse_initialized  # noqa: PLW0603
    if _langfuse_initialized:
        return True

    with _init_lock:
        # Re-check inside the lock — another thread may have initialized while we waited.
        if _langfuse_initialized:
            return True

        settings = get_langfuse_settings()
        if settings.enabled and settings.public_key and settings.secret_key:
            try:
                Langfuse(
                    public_key=settings.public_key,
                    secret_key=settings.secret_key,
                    host=settings.host,
                )
                _langfuse_initialized = True
                logger.info("Langfuse tracing initialized successfully")
            except Exception:
                logger.exception("Failed to initialize Langfuse")
                return False
        else:
            logger.info("Langfuse tracing disabled or not configured")
    return _langfuse_initialized


def is_langfuse_initialized() -> bool:
    """Return True if the Langfuse client has been successfully initialised."""
    return _langfuse_initialized


def get_langfuse_handler() -> LangfuseCallbackHandler | None:
    """
    Return a new LangChain callback handler wired to the Langfuse client.

    Returns None when Langfuse has not been initialised so callers can safely
    skip attaching callbacks without extra guards.
    """
    if not _langfuse_initialized:
        return None
    return LangfuseCallbackHandler()


def flush_langfuse() -> None:
    """Flush pending Langfuse events synchronously; swallows errors so callers stay clean.

    Note: flushes the global client queue — may include events from other concurrent
    requests. Prefer ``flush_langfuse_async`` inside async contexts so the event loop
    is not blocked while waiting.
    """
    if not _langfuse_initialized:
        return
    try:
        get_client().flush()
    except Exception:
        logger.exception("Failed to flush Langfuse events")


async def flush_langfuse_async() -> None:
    """Schedule a non-blocking Langfuse flush from an async context.

    Runs ``flush_langfuse`` in the default thread-pool executor so the async
    event loop is not blocked while the SDK drains its queue.  Fire-and-forget:
    the coroutine returns immediately after scheduling the work.
    """
    if not _langfuse_initialized:
        return
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, flush_langfuse)


__all__ = [
    "LangfuseCallbackHandler",
    "flush_langfuse",
    "flush_langfuse_async",
    "get_client",
    "get_langfuse_handler",
    "init_langfuse",
    "is_langfuse_initialized",
    "propagate_attributes",
]
