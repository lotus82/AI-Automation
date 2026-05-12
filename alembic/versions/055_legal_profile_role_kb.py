"""legal_profiles: system_role_id (FK training_scenarios), knowledge_item_ids JSONB."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "055_lp_role_kb"
down_revision = "054_compl_module"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "legal_profiles",
        sa.Column("system_role_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "legal_profiles",
        sa.Column(
            "knowledge_item_ids",
            JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_legal_profiles_system_role_id",
        "legal_profiles",
        "training_scenarios",
        ["system_role_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_legal_profiles_system_role_id", "legal_profiles", ["system_role_id"])


def downgrade() -> None:
    op.drop_index("ix_legal_profiles_system_role_id", table_name="legal_profiles")
    op.drop_constraint("fk_legal_profiles_system_role_id", "legal_profiles", type_="foreignkey")
    op.drop_column("legal_profiles", "knowledge_item_ids")
    op.drop_column("legal_profiles", "system_role_id")
