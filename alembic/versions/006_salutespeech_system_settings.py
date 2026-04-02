"""Ключи SaluteSpeech в system_settings (панель настроек).

Revision ID: 006_salutespeech_settings
Revises: 005_system_settings
Create Date: 2026-04-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text as sa_text

revision = "006_salutespeech_settings"
down_revision = "005_system_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    rows = [
        (
            "SALUTESPEECH_AUTH_KEY",
            "",
            "Ключ авторизации SaluteSpeech (Authorization Key из Studio; приоритет над env SALUTESPEECH_AUTH_KEY).",
        ),
        (
            "SALUTESPEECH_SCOPE",
            "SALUTE_SPEECH_PERS",
            "OAuth scope SaluteSpeech (как в проекте Studio: SALUTE_SPEECH_PERS, SALUTE_SPEECH_CORP и т.д.).",
        ),
        (
            "SALUTESPEECH_VOICE",
            "Ost_24000",
            "Голос синтеза SaluteSpeech (например Ost_24000, Kira_24000); для телефонии downstream остаётся 24 kHz после ресэмплинга.",
        ),
    ]
    ins = sa_text(
        """
        INSERT INTO system_settings (key, value, description)
        VALUES (:key, :value, :description)
        ON CONFLICT (key) DO NOTHING
        """
    )
    for key, value, description in rows:
        conn.execute(ins, {"key": key, "value": value, "description": description})


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM system_settings WHERE key IN "
            "('SALUTESPEECH_AUTH_KEY', 'SALUTESPEECH_SCOPE', 'SALUTESPEECH_VOICE')"
        )
    )
