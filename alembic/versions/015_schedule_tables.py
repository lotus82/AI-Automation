"""Таблицы расписания: schedules, scheduled_events (фаза 18).

Revision ID: 015_schedule_tables
Revises: 014_max_group_chat
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "015_schedule_tables"
down_revision = "014_max_group_chat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schedules",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("chat_id", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("content_template", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("interval_settings", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("reminder_offset_minutes", sa.Integer(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_schedules_chat_id", "schedules", ["chat_id"])

    op.create_table(
        "scheduled_events",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("schedule_id", UUID(as_uuid=True), nullable=False),
        sa.Column("event_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_data", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["schedules.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_scheduled_events_schedule_id", "scheduled_events", ["schedule_id"])


def downgrade() -> None:
    op.drop_index("ix_scheduled_events_schedule_id", table_name="scheduled_events")
    op.drop_table("scheduled_events")
    op.drop_index("ix_schedules_chat_id", table_name="schedules")
    op.drop_table("schedules")
