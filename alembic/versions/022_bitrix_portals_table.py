"""Таблица bitrix_portals: OAuth порталов Bitrix24 (Marketplace Server App).

Revision ID: 022_bitrix_portals
Revises: 021_max_call_voip
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "022_bitrix_portals"
down_revision = "021_max_call_voip"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bitrix_portals",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("portal_url", sa.String(length=512), nullable=False),
        sa.Column("member_id", sa.String(length=128), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("portal_url"),
        sa.UniqueConstraint("member_id"),
    )


def downgrade() -> None:
    op.drop_table("bitrix_portals")
