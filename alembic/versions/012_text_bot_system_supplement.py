"""Дополнение к системному промпту для текстовых ботов MAX/Telegram.

Revision ID: 012_text_bot_supplement
Revises: 011_max_polling
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text as sa_text

revision = "012_text_bot_supplement"
down_revision = "011_max_polling"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    ins = sa_text(
        """
        INSERT INTO system_settings (key, value, description, updated_at)
        VALUES (:key, :value, :description, now())
        ON CONFLICT (key) DO NOTHING
        """
    )
    conn.execute(
        ins,
        {
            "key": "TEXT_BOT_SYSTEM_SUPPLEMENT",
            "value": "",
            "description": (
                "Дополнение к системному промпту для текстовых ботов (MAX, Telegram): правила формата ответа и т.п."
            ),
        },
    )


def downgrade() -> None:
    op.execute(sa_text("DELETE FROM system_settings WHERE key = 'TEXT_BOT_SYSTEM_SUPPLEMENT'"))
