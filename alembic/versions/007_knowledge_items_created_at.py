"""Колонка created_at для сортировки списка базы знаний.

Revision ID: 007_knowledge_created_at
Revises: 006_salutespeech_settings
Create Date: 2026-04-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "007_knowledge_created_at"
down_revision = "006_salutespeech_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_items",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("knowledge_items", "created_at")
