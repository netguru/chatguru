"""
Repository port (interface) for chat history.

Concrete implementations live in adapter modules (e.g. SQLAlchemy) and are
wired in via `persistence.factory.build_chat_history_repository`.
"""

from typing import Protocol

from persistence.models import StoredAttachment, StoredChatMessage, StoredConversation


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
    ) -> str:
        """Persist one message and return its generated message ID."""
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

    # ------------------------------------------------------------------
    # Attachments
    # ------------------------------------------------------------------

    async def save_attachment(self, attachment: "StoredAttachment") -> None:
        """Persist an attachment record. ``message_id`` may be None initially."""
        ...

    async def link_attachments_to_message(
        self,
        *,
        attachment_ids: list[str],
        message_id: str,
        visitor_id: str,
    ) -> None:
        """Set message_id on pre-stored attachments that still have no message."""
        ...

    async def get_attachments_for_message(
        self, message_id: str
    ) -> list["StoredAttachment"]:
        """Return all attachments linked to a given message, oldest first."""
        ...

    async def get_attachments_for_messages(
        self, message_ids: list[str]
    ) -> list["StoredAttachment"]:
        """Return attachments for multiple messages in one query, oldest first."""
        ...

    async def get_attachment(
        self, *, attachment_id: str, visitor_id: str
    ) -> "StoredAttachment | None":
        """Return attachment if it belongs to visitor_id, else None."""
        ...

    async def close(self) -> None:
        """Release database connections and other resources."""
        ...
