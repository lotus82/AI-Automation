"""Ключ MAX_BOT_TOKEN в system_settings (бот мессенджера MAX).

Revision ID: 009_max_bot_token
Revises: 008_call_audio
Create Date: 2026-04-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text as sa_text

revision = "009_max_bot_token"
down_revision = "008_call_audio"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    ins = sa_text(
        """
        INSERT INTO system_settings (key, value, description)
        VALUES (:key, :value, :description)
        ON CONFLICT (key) DO NOTHING
        """
    )
    conn.execute(
        ins,
        {
            "key": "MAX_BOT_TOKEN",
            "value": "",
            "description": "Токен бота MAX (VK); задаётся в панели «Настройки», используется вебхуком /api/max/webhook.",
        },
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM system_settings WHERE key = 'MAX_BOT_TOKEN'"))
