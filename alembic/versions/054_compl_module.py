"""Комплаенс и секретариат: legal_profiles, compliance_deadlines, legal_documents."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision id must fit alembic_version.version_num (VARCHAR(32) in this project)
revision = "054_compl_module"
down_revision = "053_mini_app_usr_fln"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legal_profiles",
        sa.Column("id", sa.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("org_type", sa.String(length=16), nullable=False),
        sa.Column("tax_system", sa.String(length=24), nullable=False),
        sa.Column(
            "general_director_name",
            sa.String(length=512),
            server_default=sa.text("''"),
            nullable=False,
        ),
        sa.Column(
            "charter_rules",
            JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
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
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", name="uq_legal_profiles_organization"),
    )
    op.create_index("ix_legal_profiles_organization_id", "legal_profiles", ["organization_id"])

    op.create_table(
        "compliance_deadlines",
        sa.Column("id", sa.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_compliance_deadlines_organization_id",
        "compliance_deadlines",
        ["organization_id"],
    )
    op.create_index("ix_compliance_deadlines_due_date", "compliance_deadlines", ["due_date"])

    op.create_table(
        "legal_documents",
        sa.Column("id", sa.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("doc_type", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'draft'"),
            nullable=False,
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
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_legal_documents_organization_id", "legal_documents", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_legal_documents_organization_id", table_name="legal_documents")
    op.drop_table("legal_documents")
    op.drop_index("ix_compliance_deadlines_due_date", table_name="compliance_deadlines")
    op.drop_index("ix_compliance_deadlines_organization_id", table_name="compliance_deadlines")
    op.drop_table("compliance_deadlines")
    op.drop_index("ix_legal_profiles_organization_id", table_name="legal_profiles")
    op.drop_table("legal_profiles")
