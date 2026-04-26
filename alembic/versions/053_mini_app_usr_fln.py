"""mini_app_users: имя и фамилия отдельно (профиль Mini App)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision id must fit alembic_version.version_num (VARCHAR(32) in this project)
revision = "053_mini_app_usr_fln"
down_revision = "052_mini_app_users_birth_date"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mini_app_users", sa.Column("first_name", sa.String(128), nullable=True))
    op.add_column("mini_app_users", sa.Column("last_name", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("mini_app_users", "last_name")
    op.drop_column("mini_app_users", "first_name")
