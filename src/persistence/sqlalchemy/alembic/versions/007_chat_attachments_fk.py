"""add FK from chat_attachments.message_id to chat_messages.id

Revision ID: 007_chat_attachments_fk
Revises: 006_chat_attachments
Create Date: 2026-05-18

"""

from collections.abc import Sequence

from alembic import op

revision: str = "007_chat_attachments_fk"
down_revision: str | None = "006_chat_attachments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # SQLite does not support ADD CONSTRAINT via ALTER TABLE, so the FK is
    # added by recreating the table (Alembic batch mode).
    with op.batch_alter_table("chat_attachments") as batch_op:
        batch_op.create_foreign_key(
            "fk_chat_attachments_message_id",
            "chat_messages",
            ["message_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("chat_attachments") as batch_op:
        batch_op.drop_constraint("fk_chat_attachments_message_id", type_="foreignkey")
