"""Настройки входящих VoIP-звонков MAX (задержка ответа и приветствие).

Revision ID: 021_max_call_voip
Revises: 020_max_voice_reply
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text as sa_text

revision = "021_max_call_voip"
down_revision = "020_max_voice_reply"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa_text(
            """
            INSERT INTO system_settings (key, value, description)
            VALUES (
                'MAX_CALL_ANSWER_DELAY',
                '6',
                'Секунды ожидания перед «снятием трубки» на входящий VoIP-звонок MAX (реалистичная задержка).'
            )
            ON CONFLICT (key) DO NOTHING
            """
        ),
    )
    conn.execute(
        sa_text(
            """
            INSERT INTO system_settings (key, value, description)
            VALUES (
                'MAX_CALL_GREETING_PHRASE',
                'Здравствуйте! Это ИИ-помощник компании. Слушаю вас.',
                'Фиксированная первая фраза в голосовом пайплайне после ответа на звонок MAX (озвучивается до первого обращения к LLM).'
            )
            ON CONFLICT (key) DO NOTHING
            """
        ),
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa_text("DELETE FROM system_settings WHERE key = 'MAX_CALL_ANSWER_DELAY'"))
    conn.execute(sa_text("DELETE FROM system_settings WHERE key = 'MAX_CALL_GREETING_PHRASE'"))
