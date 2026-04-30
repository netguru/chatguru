"""add trace_id to chat_messages

Revision ID: 004_chat_messages_trace_id
Revises: 003_unique_visitor_session
Create Date: 2026-04-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004_chat_messages_trace_id"
down_revision: str | None = "003_unique_visitor_session"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.add_column(sa.Column("trace_id", sa.String(512), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.drop_column("trace_id")
