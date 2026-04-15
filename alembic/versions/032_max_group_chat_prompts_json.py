"""JSON-карта chat_id → доп. промпт для групп MAX (MAX_GROUP_CHAT_PROMPTS).

Revision ID: 032_max_group_prompts_map
Revises: 031_registration_subtitle
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text as sa_text

revision = "032_max_group_prompts_map"
down_revision = "031_registration_subtitle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa_text(
            """
            INSERT INTO system_settings (key, value, description)
            VALUES (
                'MAX_GROUP_CHAT_PROMPTS',
                '{}',
                'JSON-объект: ключ — chat_id группы MAX (строка), значение — дополнительный системный промпт для этой группы. Устаревшие MAX_GROUP_CHAT_ID / MAX_GROUP_ADDITIONAL_PROMPT учитываются, если для session_id нет записи в этом JSON.'
            )
            ON CONFLICT (key) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute(sa_text("DELETE FROM system_settings WHERE key = 'MAX_GROUP_CHAT_PROMPTS'"))
