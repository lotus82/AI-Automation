"""Организации и пользователи портала (роли, права JSONB).

Revision ID: 026_portal_auth
Revises: 025_integrations
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "026_portal_auth"
down_revision = "025_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    op.create_table(
        "portal_users",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column("username", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column(
            "permissions",
            JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index(op.f("ix_portal_users_organization_id"), "portal_users", ["organization_id"], unique=False)
    op.create_index(op.f("ix_portal_users_role"), "portal_users", ["role"], unique=False)
    op.create_index(op.f("ix_portal_users_username"), "portal_users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_portal_users_username"), table_name="portal_users")
    op.drop_index(op.f("ix_portal_users_role"), table_name="portal_users")
    op.drop_index(op.f("ix_portal_users_organization_id"), table_name="portal_users")
    op.drop_table("portal_users")
    op.drop_table("organizations")
