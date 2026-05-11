"""
SQLAlchemy Core table definitions (portable across SQLite and PostgreSQL).

Keep in sync with Alembic revisions under ``alembic/versions/`` (columns and indexes).
"""

from sqlalchemy import (
    Column,
    DateTime,
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
