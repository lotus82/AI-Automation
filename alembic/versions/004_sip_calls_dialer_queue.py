"""Поля SIP у call_records и таблица dialer_queue (автообзвон).

Revision ID: 004_sip_dialer
Revises: 003_training
Create Date: 2026-04-02

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "004_sip_dialer"
down_revision = "003_training"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "call_records",
        sa.Column(
            "direction",
            sa.String(16),
            server_default=sa.text("'web'"),
            nullable=False,
        ),
    )
    op.add_column(
        "call_records",
        sa.Column(
            "remote_phone",
            sa.String(64),
            server_default=sa.text("''"),
            nullable=False,
        ),
    )
    op.create_table(
        "dialer_queue",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "scheduled_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_dialer_queue_status", "dialer_queue", ["status"])


def downgrade() -> None:
    op.drop_index("ix_dialer_queue_status", table_name="dialer_queue")
    op.drop_table("dialer_queue")
    op.drop_column("call_records", "remote_phone")
    op.drop_column("call_records", "direction")
