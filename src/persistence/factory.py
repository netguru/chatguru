"""
Composition root for chat history persistence.

This is the only place that should choose and construct a concrete repository
implementation. Callers elsewhere obtain a :class:`ChatHistoryRepository` via
:func:`persistence.get_chat_history_repository` or call :func:`build_chat_history_repository`
in tests with explicit ``settings`` (no reliance on process-global init).
"""

from config import PersistenceSettings, get_persistence_settings
from persistence.repository import ChatHistoryRepository
from persistence.sqlalchemy.engine import create_async_engine_from_settings
from persistence.sqlalchemy.repository import SqlAlchemyChatHistoryRepository


async def build_chat_history_repository(
    settings: PersistenceSettings | None = None,
) -> ChatHistoryRepository:
    """
    Build the configured adapter, verify connectivity, and return the repository port.

    The returned instance owns one :class:`~sqlalchemy.ext.asyncio.AsyncEngine`;
    :meth:`~ChatHistoryRepository.close` disposes it. Do not share that engine elsewhere.

    Args:
        settings: If omitted, uses :func:`config.get_persistence_settings` (production).
    """
    resolved = settings if settings is not None else get_persistence_settings()
    if not resolved.database_url:
        msg = "PERSISTENCE_DATABASE_URL is not set. Set it to enable chat history persistence."
        raise ValueError(msg)
    engine = create_async_engine_from_settings(resolved)
    repo = SqlAlchemyChatHistoryRepository(engine)
    await repo.connect()
    return repo
