"""Мероприятия: дополнительный текст под заголовком на публичной странице.

Revision ID: 031_registration_subtitle
Revises: 030_registration_notify
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "031_registration_subtitle"
down_revision = "030_registration_notify"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "registration_events",
        sa.Column("title_subtitle", sa.Text(), nullable=False, server_default=sa.text("''")),
    )
    op.alter_column("registration_events", "title_subtitle", server_default=None)


def downgrade() -> None:
    op.drop_column("registration_events", "title_subtitle")
