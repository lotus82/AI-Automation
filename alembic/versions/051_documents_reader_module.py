"""Модуль «Читатель»: documents, document_nodes, site_pages.linked_document_id."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "051_documents_reader_module"
down_revision = "050_mis_audience_pages_and_menus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("author", sa.String(512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_documents_organization_id", "documents", ["organization_id"])

    op.create_table(
        "document_nodes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", UUID(as_uuid=True), sa.ForeignKey("document_nodes.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("node_type", sa.String(16), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_index("ix_document_nodes_document_id", "document_nodes", ["document_id"])
    op.create_index("ix_document_nodes_parent_id", "document_nodes", ["parent_id"])

    op.create_check_constraint(
        "ck_document_nodes_node_type",
        "document_nodes",
        "node_type IN ('book','chapter','verse','text')",
    )

    op.add_column(
        "site_pages",
        sa.Column("linked_document_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_site_pages_linked_document_id",
        "site_pages",
        "documents",
        ["linked_document_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_site_pages_linked_document_id", "site_pages", type_="foreignkey")
    op.drop_column("site_pages", "linked_document_id")
    op.drop_constraint("ck_document_nodes_node_type", "document_nodes", type_="check")
    op.drop_table("document_nodes")
    op.drop_table("documents")
