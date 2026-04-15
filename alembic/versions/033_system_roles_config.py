"""Конфигурация системных ролей (SYSTEM_ROLES_CONFIG) — JSON в system_settings.

Revision ID: 033_system_roles
Revises: 032_max_group_prompts_map
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text as sa_text

revision = "033_system_roles"
down_revision = "032_max_group_prompts_map"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa_text(
            """
            INSERT INTO system_settings (key, value, description)
            VALUES (
                'SYSTEM_ROLES_CONFIG',
                '',
                'JSON: default_role_id, analyst_role_id, roles[{id,name,prompt}]. Пусто — используются DEFAULT_CONSULTANT_PROMPT и ANALYST_QA_PROMPT.'
            )
            ON CONFLICT (key) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute(sa_text("DELETE FROM system_settings WHERE key = 'SYSTEM_ROLES_CONFIG'"))
