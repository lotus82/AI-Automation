"""sites.site_kind: standard | mis (конструктор МИС как у сайтов)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "049_sites_site_kind"
down_revision = "048_miniapp_chat_embed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sites",
        sa.Column(
            "site_kind",
            sa.String(32),
            nullable=False,
            server_default="standard",
        ),
    )
    op.create_index("ix_sites_site_kind", "sites", ["site_kind"])


def downgrade() -> None:
    op.drop_index("ix_sites_site_kind", table_name="sites")
    op.drop_column("sites", "site_kind")
