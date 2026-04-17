"""Сообщения чатов: привязка к организации (изоляция мониторинга)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "041_chat_messages_org"
down_revision = "040_mis_max_chat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_chat_messages_organization_id", "chat_messages", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_messages_organization_id", table_name="chat_messages")
    op.drop_column("chat_messages", "organization_id")
