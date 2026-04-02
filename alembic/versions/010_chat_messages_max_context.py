"""Таблица chat_messages и настройка MAX_CONTEXT_LIMIT.

Revision ID: 010_chat_persist
Revises: 009_max_bot_token
Create Date: 2026-04-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import UUID

revision = "010_chat_persist"
down_revision = "009_max_bot_token"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_messages",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("user_display", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_messages_session_id_created", "chat_messages", ["session_id", "created_at"])
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])

    conn = op.get_bind()
    conn.execute(
        sa_text(
            """
            INSERT INTO system_settings (key, value, description)
            VALUES (
                'MAX_CONTEXT_LIMIT',
                '10',
                'Сколько последних сообщений диалога передавать в LLM (Redis + PostgreSQL).'
            )
            ON CONFLICT (key) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute(sa_text("DELETE FROM system_settings WHERE key = 'MAX_CONTEXT_LIMIT'"))
    op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_session_id_created", table_name="chat_messages")
    op.drop_table("chat_messages")
