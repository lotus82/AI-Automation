"""Настройка ENABLE_WEB_SEARCH (инструмент веб-поиска для LLM).

Revision ID: 016_enable_web_search
Revises: 015_schedule_tables
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text as sa_text

revision = "016_enable_web_search"
down_revision = "015_schedule_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa_text(
            """
            INSERT INTO system_settings (key, value, description)
            VALUES (
                'ENABLE_WEB_SEARCH',
                '1',
                'Разрешить модели вызывать веб-поиск (DuckDuckGo): 1/true — да, 0/false — нет.'
            )
            ON CONFLICT (key) DO NOTHING
            """
        ),
    )


def downgrade() -> None:
    op.execute(sa_text("DELETE FROM system_settings WHERE key = 'ENABLE_WEB_SEARCH'"))
