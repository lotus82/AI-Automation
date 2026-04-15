"""Магазины: мультиарендность, каталог, заказы, статические страницы.

Revision ID: 035_shops_mt
Revises: 034_org_scope
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text as sa_text
from sqlalchemy.dialects import postgresql

revision = "035_shops_mt"
down_revision = "034_org_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    postgresql.ENUM("new", "sale", "hot", name="shop_product_tag").create(conn, checkfirst=True)
    postgresql.ENUM(
        "new",
        "paid",
        "assembling",
        "delivering",
        "completed",
        name="shop_order_status",
    ).create(conn, checkfirst=True)

    op.create_table(
        "shop_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("shop_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("order_index", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["shop_categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_categories_shop_id", "shop_categories", ["shop_id"])
    op.create_index("ix_shop_categories_parent_id", "shop_categories", ["parent_id"])

    op.add_column("shops", sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_shops_organization_id",
        "shops",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_shops_organization_id", "shops", ["organization_id"])

    op.add_column(
        "shops",
        sa.Column(
            "settings",
            postgresql.JSONB,
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("shops", sa.Column("logo_url", sa.String(length=1024), nullable=True))

    op.execute(
        sa_text(
            """
            UPDATE shops SET settings =
                jsonb_build_object('messenger_themes', COALESCE(messenger_themes, '{}'::jsonb))
                || jsonb_strip_nulls(jsonb_build_object(
                    'seller_max_chat_id', seller_max_chat_id,
                    'seller_telegram_chat_id', seller_telegram_chat_id,
                    'seller_vk_peer_id', seller_vk_peer_id
                ))
                || CASE
                    WHEN logo_path IS NOT NULL AND trim(logo_path) <> ''
                    THEN jsonb_build_object('upload_logo_rel', logo_path)
                    ELSE '{}'::jsonb
                END
            """
        )
    )

    op.execute(
        sa_text(
            """
            UPDATE shops SET organization_id = (
                SELECT id FROM organizations ORDER BY created_at ASC LIMIT 1
            )
            WHERE organization_id IS NULL
              AND EXISTS (SELECT 1 FROM organizations LIMIT 1)
            """
        )
    )

    op.drop_constraint("uq_shops_slug", "shops", type_="unique")
    op.drop_index("ix_shops_slug", table_name="shops")
    op.create_index("ix_shops_slug", "shops", ["slug"], unique=False)
    op.create_unique_constraint("uq_shops_organization_slug", "shops", ["organization_id", "slug"])

    op.drop_column("shops", "logo_path")
    op.drop_column("shops", "messenger_themes")
    op.drop_column("shops", "seller_max_chat_id")
    op.drop_column("shops", "seller_telegram_chat_id")
    op.drop_column("shops", "seller_vk_peer_id")

    product_tag = postgresql.ENUM("new", "sale", "hot", name="shop_product_tag", create_type=False)
    op.add_column(
        "shop_products",
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_shop_products_category_id",
        "shop_products",
        "shop_categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_shop_products_category_id", "shop_products", ["category_id"])

    op.add_column(
        "shop_products",
        sa.Column("photos", postgresql.JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
    )
    op.execute(
        sa_text(
            """
            UPDATE shop_products SET photos = CASE
                WHEN photo_path IS NOT NULL AND trim(photo_path) <> ''
                THEN jsonb_build_array(photo_path)
                ELSE '[]'::jsonb
            END
            """
        )
    )
    op.add_column(
        "shop_products",
        sa.Column("tag", product_tag, nullable=True),
    )
    op.add_column(
        "shop_products",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.drop_column("shop_products", "photo_path")

    op.create_table(
        "shop_discounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("shop_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_discounts_shop_id", "shop_discounts", ["shop_id"])

    order_status = postgresql.ENUM(
        "new",
        "paid",
        "assembling",
        "delivering",
        "completed",
        name="shop_order_status",
        create_type=False,
    )
    op.create_table(
        "shop_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("shop_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            order_status,
            server_default=sa.text("'new'::shop_order_status"),
            nullable=False,
        ),
        sa.Column(
            "customer_info",
            postgresql.JSONB,
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("total_amount", sa.Numeric(14, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("delivery_address", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("delivery_status", sa.String(length=128), server_default=sa.text("''"), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_orders_shop_id", "shop_orders", ["shop_id"])

    op.create_table(
        "shop_order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price_at_time", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["shop_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["shop_products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shop_order_items_order_id", "shop_order_items", ["order_id"])
    op.create_index("ix_shop_order_items_product_id", "shop_order_items", ["product_id"])

    op.create_table(
        "shop_static_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("shop_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("content", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shop_id", "slug", name="uq_shop_static_pages_shop_slug"),
    )
    op.create_index("ix_shop_static_pages_shop_id", "shop_static_pages", ["shop_id"])
    op.create_index("ix_shop_static_pages_slug", "shop_static_pages", ["slug"])


def downgrade() -> None:
    op.drop_index("ix_shop_static_pages_slug", table_name="shop_static_pages")
    op.drop_index("ix_shop_static_pages_shop_id", table_name="shop_static_pages")
    op.drop_table("shop_static_pages")

    op.drop_index("ix_shop_order_items_product_id", table_name="shop_order_items")
    op.drop_index("ix_shop_order_items_order_id", table_name="shop_order_items")
    op.drop_table("shop_order_items")

    op.drop_index("ix_shop_orders_shop_id", table_name="shop_orders")
    op.drop_table("shop_orders")

    op.drop_index("ix_shop_discounts_shop_id", table_name="shop_discounts")
    op.drop_table("shop_discounts")

    op.add_column(
        "shop_products",
        sa.Column("photo_path", sa.String(length=512), nullable=True),
    )
    op.execute(
        sa_text(
            """
            UPDATE shop_products SET photo_path = photos->>0
            WHERE jsonb_array_length(COALESCE(photos, '[]'::jsonb)) > 0
            """
        )
    )
    op.drop_column("shop_products", "is_active")
    op.drop_column("shop_products", "tag")
    op.drop_column("shop_products", "photos")
    op.drop_index("ix_shop_products_category_id", table_name="shop_products")
    op.drop_constraint("fk_shop_products_category_id", "shop_products", type_="foreignkey")
    op.drop_column("shop_products", "category_id")

    op.add_column("shops", sa.Column("seller_vk_peer_id", sa.String(length=64), nullable=True))
    op.add_column("shops", sa.Column("seller_telegram_chat_id", sa.String(length=64), nullable=True))
    op.add_column("shops", sa.Column("seller_max_chat_id", sa.String(length=64), nullable=True))
    op.add_column(
        "shops",
        sa.Column(
            "messenger_themes",
            postgresql.JSONB,
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("shops", sa.Column("logo_path", sa.String(length=512), nullable=True))

    op.execute(
        sa_text(
            """
            UPDATE shops SET
                messenger_themes = COALESCE(settings->'messenger_themes', '{}'::jsonb),
                seller_max_chat_id = NULLIF(trim(settings->>'seller_max_chat_id'), ''),
                seller_telegram_chat_id = NULLIF(trim(settings->>'seller_telegram_chat_id'), ''),
                seller_vk_peer_id = NULLIF(trim(settings->>'seller_vk_peer_id'), ''),
                logo_path = NULLIF(trim(settings->>'upload_logo_rel'), '')
            """
        )
    )

    op.drop_constraint("uq_shops_organization_slug", "shops", type_="unique")
    op.drop_index("ix_shops_slug", table_name="shops")
    op.create_index("ix_shops_slug", "shops", ["slug"], unique=True)
    op.create_unique_constraint("uq_shops_slug", "shops", ["slug"])

    op.drop_column("shops", "logo_url")
    op.drop_column("shops", "settings")
    op.drop_constraint("fk_shops_organization_id", "shops", type_="foreignkey")
    op.drop_index("ix_shops_organization_id", table_name="shops")
    op.drop_column("shops", "organization_id")

    op.drop_index("ix_shop_categories_parent_id", table_name="shop_categories")
    op.drop_index("ix_shop_categories_shop_id", table_name="shop_categories")
    op.drop_table("shop_categories")

    op.execute(sa_text("DROP TYPE IF EXISTS shop_order_status"))
    op.execute(sa_text("DROP TYPE IF EXISTS shop_product_tag"))
