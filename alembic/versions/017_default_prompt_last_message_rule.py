"""К системному промпту консультанта добавляется правило фазы 20 (фокус на последнем сообщении).

Revision ID: 017_prompt_last_msg (≤32 символа для колонки alembic_version.version_num).
Revises: 016_enable_web_search
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text as sa_text

revision = "017_prompt_last_msg"
down_revision = "016_enable_web_search"
branch_labels = None
depends_on = None

_APPEND = (
    "\n\nFocus ONLY on answering the very last message from the user. "
    "Do not re-answer or summarize previous questions from the chat history."
)


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
        {"append": _APPEND, "marker": "very last message from the user"},
    )


def downgrade() -> None:
    # Откат без восстановления точного предыдущего текста: правило могло быть отредактировано вручную.
    pass
