"""Настройка MAX_VOICE_REPLY_ENABLED (озвучка ответов бота в MAX).

Revision ID: 020_max_voice_reply
Revises: 019_consultant_grounding
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text as sa_text

revision = "020_max_voice_reply"
down_revision = "019_consultant_grounding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa_text(
            """
            INSERT INTO system_settings (key, value, description)
            VALUES (
                'MAX_VOICE_REPLY_ENABLED',
                '0',
                'Озвучивать итоговый текстовый ответ в MAX через SaluteSpeech (WAV → uploads → вложение audio). Промежуточные сообщения не озвучиваются.'
            )
            ON CONFLICT (key) DO NOTHING
            """
        ),
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa_text("DELETE FROM system_settings WHERE key = 'MAX_VOICE_REPLY_ENABLED'"))
