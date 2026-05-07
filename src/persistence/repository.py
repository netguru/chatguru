"""
Repository port (interface) for chat history.

Concrete implementations live in adapter modules (e.g. SQLAlchemy) and are
wired in via `persistence.factory.build_chat_history_repository`.
"""

from typing import Protocol

from persistence.models import StoredChatMessage, StoredConversation


class ChatHistoryRepository(Protocol):
    """
    Port for persisting and loading chat messages and conversation metadata.

    Implementations must be database-agnostic at the call site: callers use
    this protocol only, not SQL or ORM types.
    """

    async def connect(self) -> None:
        """Verify connectivity (e.g. execute a trivial query)."""
        ...

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    async def create_conversation(
        self,
        *,
        visitor_id: str,
        session_id: str,
        title: str,
    ) -> StoredConversation:
        """Create a new conversation record. Idempotent: returns existing if session already exists."""
        ...

    async def update_conversation_title(
        self,
        *,
        visitor_id: str,
        session_id: str,
        title: str,
    ) -> None:
        """Update the title of an existing conversation. No-op if the conversation does not exist."""
        ...

    async def conversation_exists(
        self,
        *,
        visitor_id: str,
        session_id: str,
    ) -> bool:
        """Return True if a conversation row exists for the given visitor+session pair."""
        ...

    async def list_conversations(
        self,
        *,
        visitor_id: str,
    ) -> list[StoredConversation]:
        """Return all conversations for a visitor, newest first."""
        ...

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    async def append_message(  # noqa: PLR0913
        self,
        *,
        visitor_id: str,
        session_id: str,
        role: str,
        content: str,
        trace_id: str | None = None,
        sources: str | None = None,
    ) -> None:
        """Persist one message. Roles are typically ``user`` or ``assistant``."""
        ...

    async def list_messages(
        self,
        *,
        visitor_id: str,
        session_id: str,
    ) -> list[StoredChatMessage]:
        """Return messages for the session in chronological order."""
        ...

    async def trace_id_owned_by_visitor(
        self,
        *,
        trace_id: str,
        visitor_id: str,
    ) -> bool:
        """Return True if a persisted assistant message with this trace_id belongs to visitor_id."""
        ...

    async def close(self) -> None:
        """Release database connections and other resources."""
        ...
