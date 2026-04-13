"""Process-wide chat history repository (FastAPI app lifespan)."""

from sqlalchemy.exc import OperationalError

from config import get_logger, get_persistence_settings
from persistence.factory import build_chat_history_repository
from persistence.repository import ChatHistoryRepository

logger = get_logger(__name__)

_chat_history_repository: ChatHistoryRepository | None = None

_MISSING_TABLE_HINT = "Chat history tables are missing. " "Run:  make migrate"


def is_persistence_enabled() -> bool:
    """Return True when PERSISTENCE_DATABASE_URL is configured and non-empty."""
    return bool(get_persistence_settings().database_url)


async def init_persistence() -> None:
    """Initialize the process-wide chat history repository (call once at startup).

    When ``PERSISTENCE_DATABASE_URL`` is not set this is a no-op — persistence
    remains disabled and no history is stored.  Requires ``make migrate`` to have
    been run beforehand when the URL *is* set.
    """
    global _chat_history_repository  # noqa: PLW0603
    if not is_persistence_enabled():
        logger.info(
            "Chat history persistence is disabled (PERSISTENCE_DATABASE_URL not set)"
        )
        return
    if _chat_history_repository is not None:
        return
    try:
        _chat_history_repository = await build_chat_history_repository()
    except OperationalError as exc:
        exc_str = str(
            exc
        ).lower()  # SQLite: "no such table"; PostgreSQL: "relation ... does not exist"
        if "no such table" in exc_str or "does not exist" in exc_str:
            raise RuntimeError(_MISSING_TABLE_HINT) from exc
        raise
    logger.info("Chat history persistence initialized")


async def shutdown_persistence() -> None:
    """Close the chat history repository (call at shutdown)."""
    global _chat_history_repository  # noqa: PLW0603
    if _chat_history_repository is not None:
        await _chat_history_repository.close()
        _chat_history_repository = None
        logger.info("Chat history persistence shut down")


def get_chat_history_repository() -> ChatHistoryRepository | None:
    """
    Return the process-wide repository, or ``None`` when persistence is disabled.

    Returns:
        The initialized :class:`ChatHistoryRepository`, or ``None`` if
        ``PERSISTENCE_DATABASE_URL`` is not set.

    Raises:
        RuntimeError: If persistence is enabled but :func:`init_persistence` has
            not run successfully (programming error — check app startup).
    """
    if not is_persistence_enabled():
        return None
    if _chat_history_repository is None:
        msg = "Chat history repository is not initialized"
        raise RuntimeError(msg)
    return _chat_history_repository
