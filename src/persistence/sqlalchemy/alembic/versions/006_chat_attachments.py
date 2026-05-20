"""add chat_attachments table

Revision ID: 006_chat_attachments
Revises: 005_chat_messages_sources
Create Date: 2026-05-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "006_chat_attachments"
down_revision: str | None = "005_chat_messages_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_attachments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("message_id", sa.String(36), nullable=True),
        sa.Column("visitor_id", sa.String(512), nullable=False),
        sa.Column("storage_key", sa.Text, nullable=False),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(256), nullable=False),
        sa.Column("size", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_chat_attachments_message", "chat_attachments", ["message_id"])
    op.create_index(
        "idx_chat_attachments_visitor",
        "chat_attachments",
        ["visitor_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_chat_attachments_visitor", table_name="chat_attachments")
    op.drop_index("idx_chat_attachments_message", table_name="chat_attachments")
    op.drop_table("chat_attachments")
