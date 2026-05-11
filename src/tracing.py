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


def get_prompt_text(
    name: str,
    *,
    fallback: str,
    label: str = "production",
) -> str:
    """Fetch a text prompt from Langfuse, falling back to a local string on any failure.

    The Langfuse SDK caches prompts in-memory (default TTL ~60s), so calling this
    per-request is cheap — most calls are an in-process dict lookup.  Edits made
    in the Langfuse UI take effect within the cache TTL without a redeploy.

    Returns the local ``fallback`` when:
      - Langfuse is not initialised (missing creds, disabled in settings, etc.).
      - The prompt does not exist on the Langfuse server (or the configured
        ``label`` has no matching version).
      - The fetched value is empty / not a string (e.g. someone configured a
        chat prompt under this name by mistake).
      - Any network or SDK error occurs.

    Args:
        name: The prompt name as registered in Langfuse (e.g. ``CHAT_SYSTEM_PROMPT``).
        fallback: Local string to return when the remote fetch cannot be used.
            Must always be a sensible default — the chat path depends on it.
        label: Langfuse prompt label to fetch.  Defaults to ``"production"``.

    Returns:
        Either the remote prompt text or the supplied fallback.  Never raises.
    """
    if not _langfuse_initialized:
        return fallback

    try:
        prompt_obj = get_client().get_prompt(name, label=label)
    except Exception:
        logger.exception(
            "Failed to fetch Langfuse prompt %r (label=%r); using local fallback",
            name,
            label,
        )
        return fallback

    text = getattr(prompt_obj, "prompt", None)
    if not isinstance(text, str) or not text.strip():
        logger.warning(
            "Langfuse prompt %r returned empty / non-string content; using local fallback",
            name,
        )
        return fallback
    return text


__all__ = [
    "LangfuseCallbackHandler",
    "flush_langfuse",
    "flush_langfuse_async",
    "get_client",
    "get_langfuse_handler",
    "get_prompt_text",
    "init_langfuse",
    "is_langfuse_initialized",
    "propagate_attributes",
]
