"""Конструктор форм регистрации: шаблоны, мероприятия, ответы.

Revision ID: 027_registration_forms
Revises: 026_portal_auth
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "027_registration_forms"
down_revision = "026_portal_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "form_templates",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("fields", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "registration_events",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column(
            "form_template_id",
            UUID(as_uuid=True),
            sa.ForeignKey("form_templates.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("event_start_date", sa.Date(), nullable=False),
        sa.Column("event_end_date", sa.Date(), nullable=False),
        sa.Column("registration_deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "registration_closed_early",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_registration_events_form_template_id",
        "registration_events",
        ["form_template_id"],
    )
    op.create_table(
        "registration_event_schedules",
        sa.Column(
            "event_id",
            UUID(as_uuid=True),
            sa.ForeignKey("registration_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "schedule_id",
            UUID(as_uuid=True),
            sa.ForeignKey("schedules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("event_id", "schedule_id"),
    )
    op.create_index(
        "ix_registration_event_schedules_schedule_id",
        "registration_event_schedules",
        ["schedule_id"],
    )
    op.create_table(
        "registration_submissions",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "event_id",
            UUID(as_uuid=True),
            sa.ForeignKey("registration_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("answers", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_registration_submissions_event_id",
        "registration_submissions",
        ["event_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_registration_submissions_event_id", table_name="registration_submissions")
    op.drop_table("registration_submissions")
    op.drop_index("ix_registration_event_schedules_schedule_id", table_name="registration_event_schedules")
    op.drop_table("registration_event_schedules")
    op.drop_index("ix_registration_events_form_template_id", table_name="registration_events")
    op.drop_table("registration_events")
    op.drop_table("form_templates")
