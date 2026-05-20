"""Domain models for persisted chat history."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class StoredConversation:
    """A conversation record (metadata row per session)."""

    id: str
    visitor_id: str
    session_id: str
    title: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class StoredChatMessage:
    """A single stored chat message row."""

    id: str
    visitor_id: str
    session_id: str
    role: str
    content: str
    created_at: datetime
    trace_id: str | None = None
    sources: str | None = None


@dataclass(frozen=True, slots=True)
class StoredAttachment:
    """A file attachment associated with a chat message."""

    id: str
    visitor_id: str
    storage_key: str
    name: str
    mime_type: str
    size: int
    created_at: datetime
    # Null until the attachment is linked to a persisted message.
    message_id: str | None = None
