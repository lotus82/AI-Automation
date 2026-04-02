"""Колонка audio_filename для привязки WAV к записи звонка.

Revision ID: 008_call_audio
Revises: 007_knowledge_created_at
Create Date: 2026-04-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "008_call_audio"
down_revision = "007_knowledge_created_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "call_records",
        sa.Column("audio_filename", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("call_records", "audio_filename")
