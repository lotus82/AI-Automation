"""medical_patients.doctor_id: nullable для карты без назначенного врача (гость МИС)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision id ≤ 32 chars: alembic_version.version_num is VARCHAR(32)
revision = "057_med_pat_dr_null"
down_revision = "056_fix_legal_role_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "medical_patients",
        "doctor_id",
        existing_type=UUID(as_uuid=True),
        nullable=True,
        existing_nullable=False,
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM medical_patients WHERE doctor_id IS NULL"))
    op.alter_column(
        "medical_patients",
        "doctor_id",
        existing_type=UUID(as_uuid=True),
        nullable=False,
        existing_nullable=True,
    )
