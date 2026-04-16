"""МИС: авторизация пациента (телефон, пароль, мессенджеры), частичные уникальные индексы."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "039_mis_patient_auth"
down_revision = "038_q_org"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("medical_patients", sa.Column("password_hash", sa.String(255), nullable=True))
    op.add_column("medical_patients", sa.Column("max_user_id", sa.String(128), nullable=True))
    op.add_column("medical_patients", sa.Column("tg_user_id", sa.String(128), nullable=True))
    op.add_column("medical_patients", sa.Column("vk_user_id", sa.String(128), nullable=True))
    op.add_column(
        "medical_patients",
        sa.Column("is_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.execute(sa.text("UPDATE medical_patients SET phone = NULL WHERE trim(COALESCE(phone, '')) = ''"))
    op.alter_column(
        "medical_patients",
        "phone",
        existing_type=sa.String(64),
        nullable=True,
        server_default=None,
    )
    op.create_index("ix_medical_patients_phone", "medical_patients", ["phone"])
    op.create_index("ix_medical_patients_max_user_id", "medical_patients", ["max_user_id"])
    op.create_index("ix_medical_patients_tg_user_id", "medical_patients", ["tg_user_id"])
    op.create_index("ix_medical_patients_vk_user_id", "medical_patients", ["vk_user_id"])
    op.create_index(
        "uq_medical_patients_org_phone_nonempty",
        "medical_patients",
        ["organization_id", "phone"],
        unique=True,
        postgresql_where=sa.text("phone IS NOT NULL AND trim(phone) <> ''"),
    )
    op.create_index(
        "uq_medical_patients_org_max_user_id_nonempty",
        "medical_patients",
        ["organization_id", "max_user_id"],
        unique=True,
        postgresql_where=sa.text("max_user_id IS NOT NULL AND trim(max_user_id) <> ''"),
    )


def downgrade() -> None:
    op.drop_index("uq_medical_patients_org_max_user_id_nonempty", table_name="medical_patients")
    op.drop_index("uq_medical_patients_org_phone_nonempty", table_name="medical_patients")
    op.drop_index("ix_medical_patients_vk_user_id", table_name="medical_patients")
    op.drop_index("ix_medical_patients_tg_user_id", table_name="medical_patients")
    op.drop_index("ix_medical_patients_max_user_id", table_name="medical_patients")
    op.drop_index("ix_medical_patients_phone", table_name="medical_patients")
    op.drop_column("medical_patients", "is_verified")
    op.drop_column("medical_patients", "vk_user_id")
    op.drop_column("medical_patients", "tg_user_id")
    op.drop_column("medical_patients", "max_user_id")
    op.drop_column("medical_patients", "password_hash")
    op.execute(sa.text("UPDATE medical_patients SET phone = '' WHERE phone IS NULL"))
    op.alter_column(
        "medical_patients",
        "phone",
        existing_type=sa.String(64),
        nullable=False,
        server_default=sa.text("''"),
    )
