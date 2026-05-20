"""
SQLAlchemy Core table definitions (portable across SQLite and PostgreSQL).

Keep in sync with Alembic revisions under ``alembic/versions/`` (columns and indexes).
"""

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

metadata = MetaData()

conversations = Table(
    "conversations",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("visitor_id", String(512), nullable=False),
    Column("session_id", String(2048), nullable=False),
    Column("title", String(500), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "visitor_id", "session_id", name="uq_conversations_visitor_session"
    ),
)

Index(
    "idx_conversations_visitor",
    conversations.c.visitor_id,
    conversations.c.created_at,
)

chat_messages = Table(
    "chat_messages",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("visitor_id", String(512), nullable=False),
    Column("session_id", String(2048), nullable=False),
    Column("role", String(32), nullable=False),
    Column("content", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("trace_id", String(512), nullable=True),
    Column("sources", Text, nullable=True),
)

Index(
    "idx_chat_messages_session",
    chat_messages.c.visitor_id,
    chat_messages.c.session_id,
    chat_messages.c.created_at,
)

chat_attachments = Table(
    "chat_attachments",
    metadata,
    Column("id", String(36), primary_key=True),
    # Nullable: populated by the upload endpoints before the message exists,
    # then linked to the message when the WebSocket turn is persisted.
    # ON DELETE SET NULL ensures attachments are not hard-deleted when a
    # message row is removed (preserves the stored file and its metadata).
    Column(
        "message_id",
        String(36),
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("visitor_id", String(512), nullable=False),
    Column("storage_key", Text, nullable=False),
    Column("name", String(512), nullable=False),
    Column("mime_type", String(256), nullable=False),
    Column("size", BigInteger, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

Index(
    "idx_chat_attachments_message",
    chat_attachments.c.message_id,
)

Index(
    "idx_chat_attachments_visitor",
    chat_attachments.c.visitor_id,
    chat_attachments.c.created_at,
)
