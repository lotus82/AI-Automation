"""Настройки и база знаний в разрезе организации.

Revision ID: 034_org_scope
Revises: 033_system_roles
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import UUID

revision = "034_org_scope"
down_revision = "033_system_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_settings",
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("description", sa.String(length=512), nullable=False, server_default=sa.text("''")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("organization_id", "key"),
    )
    op.create_index(
        "ix_organization_settings_key",
        "organization_settings",
        ["key"],
        unique=False,
    )

    op.add_column(
        "knowledge_items",
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_knowledge_items_organization_id",
        "knowledge_items",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_knowledge_items_organization_id",
        "knowledge_items",
        ["organization_id"],
        unique=False,
    )

    # Копия глобальных настроек в каждую существующую организацию (стартовый снимок).
    conn = op.get_bind()
    org_ids = conn.execute(sa_text("SELECT id FROM organizations")).fetchall()
    rows = conn.execute(sa_text("SELECT key, value, description FROM system_settings")).fetchall()
    ins = sa_text(
        """
        INSERT INTO organization_settings (organization_id, key, value, description)
        VALUES (:oid, :key, :value, :description)
        ON CONFLICT (organization_id, key) DO NOTHING
        """
    )
    for (oid,) in org_ids:
        for key, value, description in rows:
            conn.execute(
                ins,
                {
                    "oid": oid,
                    "key": key,
                    "value": value or "",
                    "description": description or "",
                },
            )

    # Привязка существующих элементов БЗ к первой организации (если есть), иначе остаётся NULL (наследие).
    conn.execute(
        sa_text(
            """
            UPDATE knowledge_items ki
            SET organization_id = (SELECT id FROM organizations ORDER BY created_at ASC LIMIT 1)
            WHERE ki.organization_id IS NULL
              AND EXISTS (SELECT 1 FROM organizations LIMIT 1)
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_items_organization_id", table_name="knowledge_items")
    op.drop_constraint("fk_knowledge_items_organization_id", "knowledge_items", type_="foreignkey")
    op.drop_column("knowledge_items", "organization_id")
    op.drop_index("ix_organization_settings_key", table_name="organization_settings")
    op.drop_table("organization_settings")
