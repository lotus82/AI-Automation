"""МИС: врачи, пациенты, записи обследований."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "036_mis"
down_revision = "035_shops_mt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Создаём тип один раз. Для колонки нужен отдельный ENUM с create_type=False — иначе при
    # op.create_table SQLAlchemy снова выполнит CREATE TYPE и получится DuplicateObjectError.
    medical_entry_type = postgresql.ENUM("exam", "survey", name="medical_entry_type", create_type=True)
    medical_entry_type.create(op.get_bind(), checkfirst=True)
    medical_entry_type_col = postgresql.ENUM("exam", "survey", name="medical_entry_type", create_type=False)

    op.create_table(
        "medical_doctors",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("portal_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("qualification", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["portal_user_id"], ["portal_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("portal_user_id", name="uq_medical_doctors_portal_user"),
    )
    op.create_index("ix_medical_doctors_organization_id", "medical_doctors", ["organization_id"])
    op.create_index("ix_medical_doctors_portal_user_id", "medical_doctors", ["portal_user_id"])

    op.create_table(
        "medical_patients",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(512), nullable=False),
        sa.Column("phone", sa.String(64), server_default=sa.text("''"), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(32), nullable=True),
        sa.Column("height", sa.Float(), nullable=True),
        sa.Column("weight", sa.Float(), nullable=True),
        sa.Column("current_diagnosis", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("treatment_plan", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["doctor_id"], ["medical_doctors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_medical_patients_organization_id", "medical_patients", ["organization_id"])
    op.create_index("ix_medical_patients_doctor_id", "medical_patients", ["doctor_id"])

    op.create_table(
        "medical_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", medical_entry_type_col, nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("conclusion", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("recommendations", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["medical_patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_medical_entries_patient_id", "medical_entries", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_medical_entries_patient_id", table_name="medical_entries")
    op.drop_table("medical_entries")
    op.drop_index("ix_medical_patients_doctor_id", table_name="medical_patients")
    op.drop_index("ix_medical_patients_organization_id", table_name="medical_patients")
    op.drop_table("medical_patients")
    op.drop_index("ix_medical_doctors_portal_user_id", table_name="medical_doctors")
    op.drop_index("ix_medical_doctors_organization_id", table_name="medical_doctors")
    op.drop_table("medical_doctors")
    op.execute(sa.text("DROP TYPE IF EXISTS medical_entry_type"))
