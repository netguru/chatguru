"""add conversations table

Revision ID: 002_conversations
Revises: 001_initial
Create Date: 2026-04-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002_conversations"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("visitor_id", sa.String(length=512), nullable=False),
        sa.Column("session_id", sa.String(length=2048), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_conversations_visitor",
        "conversations",
        ["visitor_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_conversations_visitor", table_name="conversations")
    op.drop_table("conversations")
