"""mini_app_users: дата рождения (Mini App «Профиль» + поздравления)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "052_mini_app_users_birth_date"
down_revision = "051_documents_reader_module"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mini_app_users",
        sa.Column("birth_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mini_app_users", "birth_date")
