"""Описание фрагмента базы знаний (поле description).

Revision ID: 013_knowledge_desc
Revises: 012_text_bot_supplement
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "013_knowledge_desc"
down_revision = "012_text_bot_supplement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_items",
        sa.Column("description", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_items", "description")
