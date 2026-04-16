"""МИС: идентификатор личного чата MAX у пациента (регистрация через бота)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "040_mis_max_chat"
down_revision = "039_mis_patient_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("medical_patients", sa.Column("max_chat_id", sa.String(64), nullable=True))
    op.create_index("ix_medical_patients_max_chat_id", "medical_patients", ["max_chat_id"])
    op.create_index(
        "uq_medical_patients_org_max_chat_id_nonempty",
        "medical_patients",
        ["organization_id", "max_chat_id"],
        unique=True,
        postgresql_where=sa.text("max_chat_id IS NOT NULL AND trim(max_chat_id) <> ''"),
    )


def downgrade() -> None:
    op.drop_index("uq_medical_patients_org_max_chat_id_nonempty", table_name="medical_patients")
    op.drop_index("ix_medical_patients_max_chat_id", table_name="medical_patients")
    op.drop_column("medical_patients", "max_chat_id")
