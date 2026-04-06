"""Дополнение промпта консультанта: не выдумывать факты (фаза 21).

Revision ID: 019_consultant_grounding
Revises: 018_llm_temperature
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text as sa_text

revision = "019_consultant_grounding"
down_revision = "018_llm_temperature"
branch_labels = None
depends_on = None

_APPEND = (
    "\n\nНикогда не выдумывай факты, которых нет в базе знаний или в результатах поиска. "
    "Если не уверен — скажи, что не знаешь."
)
_MARKER = "никогда не выдумывай факты"


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa_text(
            """
            UPDATE system_settings
            SET value = value || :append
            WHERE key = 'DEFAULT_CONSULTANT_PROMPT'
              AND position(lower(:marker) in lower(value)) = 0
            """
        ),
        {"append": _APPEND, "marker": _MARKER},
    )


def downgrade() -> None:
    pass
