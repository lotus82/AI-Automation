"""Таблицы опросников: questionnaires, questions, question_options.

Revision ID: 024_questionnaires
Revises: 023_trainer_ai
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "024_questionnaires"
down_revision = "023_trainer_ai"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "questionnaires",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("llm_criteria", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "questions",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "questionnaire_id",
            UUID(as_uuid=True),
            sa.ForeignKey("questionnaires.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("min_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_score", sa.Float(), nullable=False, server_default=sa.text("10")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_questions_questionnaire_id", "questions", ["questionnaire_id"])
    op.create_table(
        "question_options",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "question_id",
            UUID(as_uuid=True),
            sa.ForeignKey("questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_question_options_question_id", "question_options", ["question_id"])


def downgrade() -> None:
    op.drop_index("ix_question_options_question_id", table_name="question_options")
    op.drop_table("question_options")
    op.drop_index("ix_questions_questionnaire_id", table_name="questions")
    op.drop_table("questions")
    op.drop_table("questionnaires")
