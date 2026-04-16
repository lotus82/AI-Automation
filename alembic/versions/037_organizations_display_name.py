"""Краткое имя организации для панели (шапка, селектор)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "037_org_display"
down_revision = "036_mis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("display_name", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organizations", "display_name")
