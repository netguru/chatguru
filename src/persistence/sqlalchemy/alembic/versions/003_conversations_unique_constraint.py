"""add unique constraint on conversations(visitor_id, session_id)

Revision ID: 003_unique_visitor_session
Revises: 002_conversations
Create Date: 2026-04-10

"""

from collections.abc import Sequence

from alembic import op

revision: str = "003_unique_visitor_session"
down_revision: str | None = "002_conversations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.create_unique_constraint(
            "uq_conversations_visitor_session",
            ["visitor_id", "session_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.drop_constraint(
            "uq_conversations_visitor_session",
            type_="unique",
        )
