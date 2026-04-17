"""Привязка активного сайта к организации: organizations.active_site_id.

FK с ON DELETE SET NULL: если сайт удалён, организация остаётся без привязки к
Mini App-сайту; перед удалением organizations FK должен быть снят (см. downgrade).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "044_org_active_site"
down_revision = "043_sites_and_pages"
branch_labels = None
depends_on = None


_FK_NAME = "fk_organizations_active_site_id"


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("active_site_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_organizations_active_site_id",
        "organizations",
        ["active_site_id"],
    )
    op.create_foreign_key(
        _FK_NAME,
        source_table="organizations",
        referent_table="sites",
        local_cols=["active_site_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(_FK_NAME, "organizations", type_="foreignkey")
    op.drop_index("ix_organizations_active_site_id", table_name="organizations")
    op.drop_column("organizations", "active_site_id")
