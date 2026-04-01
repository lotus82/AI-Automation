"""Таблицы call_records и call_analytics для ОКК и дашборда.

Revision ID: 002_call_analytics
Revises: 001_initial
Create Date: 2026-04-02

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "002_call_analytics"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "call_records",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("duration", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("transcript_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_call_records_session_id", "call_records", ["session_id"])

    op.create_table(
        "call_analytics",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("call_record_id", UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("recommendations", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["call_record_id"],
            ["call_records.id"],
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    op.drop_table("call_analytics")
    op.drop_index("ix_call_records_session_id", table_name="call_records")
    op.drop_table("call_records")
