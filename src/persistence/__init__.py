"""
Persistence package: repository port, factory, migrations, and bootstrap.

Import lifecycle helpers from the package root (re-exported from :mod:`persistence.bootstrap`).
"""

from persistence.bootstrap import (
    get_chat_history_repository,
    init_persistence,
    is_persistence_enabled,
    shutdown_persistence,
)
from persistence.factory import build_chat_history_repository
from persistence.models import StoredChatMessage, StoredConversation
from persistence.repository import ChatHistoryRepository
from persistence.sqlalchemy.migrate import upgrade_head

__all__ = [
    "ChatHistoryRepository",
    "StoredChatMessage",
    "StoredConversation",
    "build_chat_history_repository",
    "get_chat_history_repository",
    "init_persistence",
    "is_persistence_enabled",
    "shutdown_persistence",
    "upgrade_head",
]
