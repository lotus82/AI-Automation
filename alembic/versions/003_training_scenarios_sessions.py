"""Таблицы training_scenarios и training_sessions (тренажёр менеджеров).

Revision ID: 003_training
Revises: 002_call_analytics
Create Date: 2026-04-02

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "003_training"
down_revision = "002_call_analytics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "training_scenarios",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("client_persona_prompt", sa.Text(), nullable=False),
        sa.Column("objections_to_raise", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_table(
        "training_sessions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "scenario_id",
            UUID(as_uuid=True),
            sa.ForeignKey("training_scenarios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("manager_name", sa.String(255), nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("feedback_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_training_sessions_session_id", "training_sessions", ["session_id"])

    # TODO: При появлении админки массовой загрузки сценариев вынести сиды из миграции в отдельный скрипт.
    op.execute(
        r"""
        INSERT INTO training_scenarios (title, client_persona_prompt, objections_to_raise)
        SELECT
            $title$Недоверчивый клиент, покупающий фрезерный станок из Китая, который жалуется на сроки доставки$title$,
            $persona$Ты играешь роль руководителя небольшого механического цеха в России. Ищешь фрезерный станок с ЧПУ из Китая, бюджет ограничен, опыта закупок из КНР мало. Тон настороженный: переспрашиваешь, сомневаешься в честности поставщика. Отвечай короткими фразами, как в телефонном разговоре. Не говори, что ты ИИ.$persona$,
            $obj$— Сроки доставки: «Опять два месяца обещают, а по факту полгода».
— Таможня и документы: «Кто отвечает, если застрянет на границе?»
— Качество и сервис: «Китайский станок — через год только ремонтировать».
— Цена: «У конкурента дешевле, чем вы докажете, что ваша сделка лучше?»$obj$
        WHERE NOT EXISTS (SELECT 1 FROM training_scenarios LIMIT 1)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_training_sessions_session_id", table_name="training_sessions")
    op.drop_table("training_sessions")
    op.drop_table("training_scenarios")
