"""Мероприятия: уведомления в чат мессенджера при новой регистрации.

Revision ID: 030_registration_notify
Revises: 029_shop_cart
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "030_registration_notify"
down_revision = "029_shop_cart"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "registration_events",
        sa.Column("notify_messenger", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "registration_events",
        sa.Column("notify_chat_id", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("registration_events", "notify_chat_id")
    op.drop_column("registration_events", "notify_messenger")
