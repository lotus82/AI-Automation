"""Ключ MAX_USE_POLLING: long polling MAX для локальной отладки.

Revision ID: 011_max_polling
Revises: 010_chat_persist
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text as sa_text

revision = "011_max_polling"
down_revision = "010_chat_persist"
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
            "key": "MAX_USE_POLLING",
            "value": "1",
            "description": (
                "Long polling обновлений MAX (GET /updates); для продакшена выключите и используйте Webhook. См. README."
            ),
        },
    )


def downgrade() -> None:
    op.execute(sa_text("DELETE FROM system_settings WHERE key = 'MAX_USE_POLLING'"))
