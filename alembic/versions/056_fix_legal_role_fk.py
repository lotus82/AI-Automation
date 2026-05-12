"""legal_profiles.system_role_id: убрать FK на training_scenarios, тип String."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "056_fix_legal_role_fk"
down_revision = "055_lp_role_kb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("fk_legal_profiles_system_role_id", "legal_profiles", type_="foreignkey")
    op.alter_column(
        "legal_profiles",
        "system_role_id",
        existing_type=UUID(as_uuid=True),
        type_=sa.String(length=128),
        postgresql_using="system_role_id::text",
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "legal_profiles",
        "system_role_id",
        existing_type=sa.String(length=128),
        type_=UUID(as_uuid=True),
        postgresql_using=(
            "CASE "
            "WHEN system_role_id IS NULL OR btrim(system_role_id) = '' THEN NULL::uuid "
            "WHEN system_role_id ~* "
            "'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' "
            "THEN system_role_id::uuid ELSE NULL::uuid END"
        ),
        existing_nullable=True,
    )
    op.create_foreign_key(
        "fk_legal_profiles_system_role_id",
        "legal_profiles",
        "training_scenarios",
        ["system_role_id"],
        ["id"],
        ondelete="SET NULL",
    )
