"""Таблицы онлайн-записи: booking_configs, booking_busy_slots, booking_appointments."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "046_booking_tables"
down_revision = "045_sites_menu_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "booking_configs",
        sa.Column("id", sa.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("portal_user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("working_hours", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("appointment_duration", sa.Integer(), server_default=sa.text("30"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["portal_user_id"], ["portal_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("portal_user_id", "organization_id", name="uq_booking_configs_user_org"),
    )
    op.create_index("ix_booking_configs_portal_user_id", "booking_configs", ["portal_user_id"])
    op.create_index("ix_booking_configs_organization_id", "booking_configs", ["organization_id"])

    op.create_table(
        "booking_busy_slots",
        sa.Column("id", sa.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("portal_user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(512), server_default=sa.text("''"), nullable=False),
        sa.ForeignKeyConstraint(["portal_user_id"], ["portal_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_booking_busy_slots_portal_user_id", "booking_busy_slots", ["portal_user_id"])
    op.create_index("ix_booking_busy_slots_start_time", "booking_busy_slots", ["start_time"])

    op.create_table(
        "booking_appointments",
        sa.Column("id", sa.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("portal_user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("client_info", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("service_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["portal_user_id"], ["portal_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_booking_appointments_portal_user_id", "booking_appointments", ["portal_user_id"])
    op.create_index("ix_booking_appointments_organization_id", "booking_appointments", ["organization_id"])
    op.create_index("ix_booking_appointments_start_time", "booking_appointments", ["start_time"])


def downgrade() -> None:
    op.drop_index("ix_booking_appointments_start_time", table_name="booking_appointments")
    op.drop_index("ix_booking_appointments_organization_id", table_name="booking_appointments")
    op.drop_index("ix_booking_appointments_portal_user_id", table_name="booking_appointments")
    op.drop_table("booking_appointments")
    op.drop_index("ix_booking_busy_slots_start_time", table_name="booking_busy_slots")
    op.drop_index("ix_booking_busy_slots_portal_user_id", table_name="booking_busy_slots")
    op.drop_table("booking_busy_slots")
    op.drop_index("ix_booking_configs_organization_id", table_name="booking_configs")
    op.drop_index("ix_booking_configs_portal_user_id", table_name="booking_configs")
    op.drop_table("booking_configs")
