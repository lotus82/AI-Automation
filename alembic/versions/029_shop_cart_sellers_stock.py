"""Магазины: остатки товаров, ID продавца в мессенджерах для уведомлений о заказах.

Revision ID: 029_shop_cart
Revises: 028_shops
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "029_shop_cart"
down_revision = "028_shops"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shop_products",
        sa.Column("stock_quantity", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.alter_column("shop_products", "stock_quantity", server_default=None)

    op.add_column("shops", sa.Column("seller_max_chat_id", sa.String(length=64), nullable=True))
    op.add_column("shops", sa.Column("seller_telegram_chat_id", sa.String(length=64), nullable=True))
    op.add_column("shops", sa.Column("seller_vk_peer_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("shops", "seller_vk_peer_id")
    op.drop_column("shops", "seller_telegram_chat_id")
    op.drop_column("shops", "seller_max_chat_id")
    op.drop_column("shop_products", "stock_quantity")
