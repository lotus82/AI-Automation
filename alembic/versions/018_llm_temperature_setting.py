"""Настройка LLM_TEMPERATURE (креативность ответов консультанта и расписания).

Revision ID: 018_llm_temperature
Revises: 017_prompt_last_msg
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text as sa_text

revision = "018_llm_temperature"
down_revision = "017_prompt_last_msg"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa_text(
            """
            INSERT INTO system_settings (key, value, description)
            VALUES (
                'LLM_TEMPERATURE',
                '0.2',
                'Температура LLM для чата консультанта и проактивных сообщений (0.0–1.0). Ниже — точнее, выше — свободнее.'
            )
            ON CONFLICT (key) DO NOTHING
            """
        ),
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa_text("DELETE FROM system_settings WHERE key = 'LLM_TEMPERATURE'"))
