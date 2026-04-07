"""Таблицы trainer_methodologies и ai_trainer_sessions (ИИ-тренер BANT/MEDDIC + симуляции).

Revision ID: 023_trainer_ai
Revises: 022_bitrix_portals
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "023_trainer_ai"
down_revision = "022_bitrix_portals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trainer_methodologies",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("client_role_system_prompt", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "ai_trainer_sessions",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("manager_id", sa.String(length=255), nullable=False),
        sa.Column("session_type", sa.String(length=32), nullable=False),
        sa.Column("result_data", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("methodology_id", UUID(as_uuid=True), nullable=True),
        sa.Column("scenario_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["methodology_id"],
            ["trainer_methodologies.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["training_scenarios.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_ai_trainer_sessions_manager_id", "ai_trainer_sessions", ["manager_id"])
    op.create_index("ix_ai_trainer_sessions_session_type", "ai_trainer_sessions", ["session_type"])

    op.execute(
        sa.text(
            """
            INSERT INTO trainer_methodologies (code, name, description, client_role_system_prompt)
            VALUES
            (
              'bant',
              'BANT',
              'Квалификация по Budget, Authority, Need, Timeline.',
              'Ты — заказчик B2B. Отвечай кратко по-русски. Не раскрывай бюджет и ЛПР без уважительных вопросов менеджера.'
            ),
            (
              'meddic',
              'MEDDIC',
              'Квалификация по Metrics, Economic buyer, Decision criteria, Decision process, Identify pain, Champion.',
              'Ты — директор по закупкам промышленного предприятия. Сомневаешься в качестве, скрываешь бюджет, неохотно идёшь на контакт. Отвечай коротко по-русски.'
            );
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_ai_trainer_sessions_session_type", table_name="ai_trainer_sessions")
    op.drop_index("ix_ai_trainer_sessions_manager_id", table_name="ai_trainer_sessions")
    op.drop_table("ai_trainer_sessions")
    op.drop_table("trainer_methodologies")
