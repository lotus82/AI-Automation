"""Опросники: привязка к организации."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "038_q_org"
down_revision = "037_org_display"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "questionnaires",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_questionnaires_organization_id", "questionnaires", ["organization_id"])
    op.create_foreign_key(
        "fk_questionnaires_organization_id",
        "questionnaires",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_questionnaires_organization_id", "questionnaires", type_="foreignkey")
    op.drop_index("ix_questionnaires_organization_id", table_name="questionnaires")
    op.drop_column("questionnaires", "organization_id")
