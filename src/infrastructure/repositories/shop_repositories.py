"""Репозитории магазинов: все выборки ограничены ``organization_id`` тенанта."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.infrastructure.models import (
    CategoryModel,
    DiscountModel,
    OrderItemModel,
    OrderModel,
    ProductModel,
    ShopModel,
    ShopOrderStatus,
    ShopProductTag,
    StaticPageModel,
)


class SqlAlchemyShopRepository:
    """CRUD по магазинам в рамках организации."""

    def __init__(self, session: AsyncSession, *, organization_id: UUID | None) -> None:
        self._session = session
        self._organization_id = organization_id

    def _org_match(self) -> Any:
        if self._organization_id is None:
            return ShopModel.organization_id.is_(None)
        return ShopModel.organization_id == self._organization_id

    async def list_shops(self) -> Sequence[ShopModel]:
        stmt = select(ShopModel).where(self._org_match()).order_by(ShopModel.updated_at.desc())
        return (await self._session.scalars(stmt)).all()

    async def get_shop(self, shop_id: UUID) -> ShopModel | None:
        row = await self._session.get(ShopModel, shop_id)
        if row is None:
            return None
        if self._organization_id is None:
            if row.organization_id is not None:
                return None
        elif row.organization_id != self._organization_id:
            return None
        return row

    async def create_shop(
        self,
        *,
        name: str,
        slug: str,
        description: str = "",
        logo_url: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> ShopModel:
        row = ShopModel(
            organization_id=self._organization_id,
            name=name.strip(),
            slug=slug.strip().lower(),
            description=(description or "").strip(),
            logo_url=(logo_url or "").strip() or None,
            settings=dict(settings or {}),
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def update_shop(
        self,
        shop_id: UUID,
        *,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
        logo_url: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> ShopModel | None:
        row = await self.get_shop(shop_id)
        if row is None:
            return None
        if name is not None:
            row.name = name.strip()
        if slug is not None:
            row.slug = slug.strip().lower()
        if description is not None:
            row.description = description.strip()
        if logo_url is not None:
            row.logo_url = (logo_url or "").strip() or None
        if settings is not None:
            row.settings = dict(settings)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def delete_shop(self, shop_id: UUID) -> bool:
        row = await self.get_shop(shop_id)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True


class _ShopScopedRepo:
    """Проверка принадлежности ``shop_id`` организации."""

    def __init__(self, session: AsyncSession, *, organization_id: UUID | None) -> None:
        self._session = session
        self._organization_id = organization_id

    async def _get_shop_in_org(self, shop_id: UUID) -> ShopModel | None:
        stmt = select(ShopModel).where(
            ShopModel.id == shop_id,
            ShopModel.organization_id == self._organization_id
            if self._organization_id is not None
            else ShopModel.organization_id.is_(None),
        )
        return (await self._session.scalars(stmt)).first()


class SqlAlchemyCategoryRepository(_ShopScopedRepo):
    async def list_categories(self, shop_id: UUID) -> Sequence[CategoryModel]:
        if await self._get_shop_in_org(shop_id) is None:
            return []
        stmt = (
            select(CategoryModel)
            .where(CategoryModel.shop_id == shop_id)
            .order_by(CategoryModel.order_index, CategoryModel.name)
        )
        return (await self._session.scalars(stmt)).all()

    async def get_category(self, shop_id: UUID, category_id: UUID) -> CategoryModel | None:
        if await self._get_shop_in_org(shop_id) is None:
            return None
        row = await self._session.get(CategoryModel, category_id)
        if row is None or row.shop_id != shop_id:
            return None
        return row

    async def create_category(
        self,
        shop_id: UUID,
        *,
        name: str,
        description: str = "",
        parent_id: UUID | None = None,
        order_index: int = 0,
    ) -> CategoryModel | None:
        if await self._get_shop_in_org(shop_id) is None:
            return None
        row = CategoryModel(
            shop_id=shop_id,
            parent_id=parent_id,
            name=name.strip(),
            description=(description or "").strip(),
            order_index=order_index,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def update_category(
        self,
        shop_id: UUID,
        category_id: UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        order_index: int | None = None,
    ) -> CategoryModel | None:
        row = await self.get_category(shop_id, category_id)
        if row is None:
            return None
        if name is not None:
            row.name = name.strip()
        if description is not None:
            row.description = description.strip()
        if order_index is not None:
            row.order_index = order_index
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def delete_category(self, shop_id: UUID, category_id: UUID) -> bool:
        row = await self.get_category(shop_id, category_id)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True


class SqlAlchemyShopProductRepository(_ShopScopedRepo):
    async def list_products(self, shop_id: UUID, *, active_only: bool = False) -> Sequence[ProductModel]:
        if await self._get_shop_in_org(shop_id) is None:
            return []
        stmt = select(ProductModel).where(ProductModel.shop_id == shop_id)
        if active_only:
            stmt = stmt.where(ProductModel.is_active.is_(True))
        stmt = stmt.order_by(ProductModel.sort_order, ProductModel.name)
        return (await self._session.scalars(stmt)).all()

    async def get_product(self, shop_id: UUID, product_id: UUID) -> ProductModel | None:
        if await self._get_shop_in_org(shop_id) is None:
            return None
        row = await self._session.get(ProductModel, product_id)
        if row is None or row.shop_id != shop_id:
            return None
        return row

    async def create_product(
        self,
        shop_id: UUID,
        *,
        name: str,
        price: Decimal,
        description: str = "",
        stock_quantity: int = 0,
        category_id: UUID | None = None,
        photos: list[str] | None = None,
        tag: ShopProductTag | None = None,
        is_active: bool = True,
        sort_order: int = 0,
    ) -> ProductModel | None:
        if await self._get_shop_in_org(shop_id) is None:
            return None
        row = ProductModel(
            shop_id=shop_id,
            category_id=category_id,
            name=name.strip(),
            description=(description or "").strip(),
            price=price,
            photos=list(photos or []),
            stock_quantity=stock_quantity,
            tag=tag,
            is_active=is_active,
            sort_order=sort_order,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def update_product(
        self,
        shop_id: UUID,
        product_id: UUID,
        **fields: Any,
    ) -> ProductModel | None:
        row = await self.get_product(shop_id, product_id)
        if row is None:
            return None
        for key, val in fields.items():
            if val is None and key not in ("category_id", "tag"):
                continue
            if hasattr(row, key):
                setattr(row, key, val)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def delete_product(self, shop_id: UUID, product_id: UUID) -> bool:
        row = await self.get_product(shop_id, product_id)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True


class SqlAlchemyDiscountRepository(_ShopScopedRepo):
    async def list_discounts(self, shop_id: UUID) -> Sequence[DiscountModel]:
        if await self._get_shop_in_org(shop_id) is None:
            return []
        stmt = select(DiscountModel).where(DiscountModel.shop_id == shop_id).order_by(DiscountModel.start_date.desc())
        return (await self._session.scalars(stmt)).all()

    async def create_discount(
        self,
        shop_id: UUID,
        *,
        name: str,
        percentage: Decimal,
        start_date: date,
        end_date: date,
    ) -> DiscountModel | None:
        if await self._get_shop_in_org(shop_id) is None:
            return None
        row = DiscountModel(
            shop_id=shop_id,
            name=name.strip(),
            percentage=percentage,
            start_date=start_date,
            end_date=end_date,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def delete_discount(self, shop_id: UUID, discount_id: UUID) -> bool:
        if await self._get_shop_in_org(shop_id) is None:
            return False
        row = await self._session.get(DiscountModel, discount_id)
        if row is None or row.shop_id != shop_id:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True


class SqlAlchemyShopOrderRepository(_ShopScopedRepo):
    async def list_orders(self, shop_id: UUID) -> Sequence[OrderModel]:
        if await self._get_shop_in_org(shop_id) is None:
            return []
        stmt = select(OrderModel).where(OrderModel.shop_id == shop_id).order_by(OrderModel.id.desc())
        return (await self._session.scalars(stmt)).all()

    async def list_orders_with_items(self, shop_id: UUID) -> Sequence[OrderModel]:
        if await self._get_shop_in_org(shop_id) is None:
            return []
        stmt = (
            select(OrderModel)
            .where(OrderModel.shop_id == shop_id)
            .options(selectinload(OrderModel.items))
            .order_by(OrderModel.id.desc())
        )
        return (await self._session.scalars(stmt)).all()

    async def get_order(self, shop_id: UUID, order_id: UUID) -> OrderModel | None:
        if await self._get_shop_in_org(shop_id) is None:
            return None
        row = await self._session.get(OrderModel, order_id)
        if row is None or row.shop_id != shop_id:
            return None
        return row

    async def create_order(
        self,
        shop_id: UUID,
        *,
        customer_info: dict[str, Any],
        total_amount: Decimal,
        delivery_address: str = "",
        delivery_status: str = "",
        status: ShopOrderStatus = ShopOrderStatus.new,
    ) -> OrderModel | None:
        if await self._get_shop_in_org(shop_id) is None:
            return None
        row = OrderModel(
            shop_id=shop_id,
            status=status,
            customer_info=dict(customer_info or {}),
            total_amount=total_amount,
            delivery_address=(delivery_address or "").strip(),
            delivery_status=(delivery_status or "").strip(),
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def add_order_item(
        self,
        shop_id: UUID,
        order_id: UUID,
        *,
        product_id: UUID,
        quantity: int,
        price_at_time: Decimal,
    ) -> OrderItemModel | None:
        order = await self.get_order(shop_id, order_id)
        if order is None:
            return None
        row = OrderItemModel(
            order_id=order_id,
            product_id=product_id,
            quantity=quantity,
            price_at_time=price_at_time,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row


class SqlAlchemyStaticPageRepository(_ShopScopedRepo):
    async def list_pages(self, shop_id: UUID) -> Sequence[StaticPageModel]:
        if await self._get_shop_in_org(shop_id) is None:
            return []
        stmt = select(StaticPageModel).where(StaticPageModel.shop_id == shop_id).order_by(StaticPageModel.slug)
        return (await self._session.scalars(stmt)).all()

    async def get_page_by_slug(self, shop_id: UUID, slug: str) -> StaticPageModel | None:
        if await self._get_shop_in_org(shop_id) is None:
            return None
        stmt = select(StaticPageModel).where(
            StaticPageModel.shop_id == shop_id,
            StaticPageModel.slug == slug.strip().lower(),
        )
        return (await self._session.scalars(stmt)).first()

    async def create_page(
        self,
        shop_id: UUID,
        *,
        title: str,
        slug: str,
        content: str = "",
    ) -> StaticPageModel | None:
        if await self._get_shop_in_org(shop_id) is None:
            return None
        row = StaticPageModel(
            shop_id=shop_id,
            title=title.strip(),
            slug=slug.strip().lower(),
            content=(content or "").strip(),
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def update_page(
        self,
        shop_id: UUID,
        page_id: UUID,
        *,
        title: str | None = None,
        slug: str | None = None,
        content: str | None = None,
    ) -> StaticPageModel | None:
        if await self._get_shop_in_org(shop_id) is None:
            return None
        pg = await self._session.get(StaticPageModel, page_id)
        if pg is None or pg.shop_id != shop_id:
            return None
        if title is not None:
            pg.title = title.strip()
        if slug is not None:
            s = slug.strip().lower()
            stmt = select(StaticPageModel).where(
                and_(
                    StaticPageModel.shop_id == shop_id,
                    StaticPageModel.slug == s,
                    StaticPageModel.id != page_id,
                ),
            )
            if (await self._session.scalars(stmt)).first() is not None:
                return None
            pg.slug = s
        if content is not None:
            pg.content = content.strip()
        await self._session.flush()
        await self._session.refresh(pg)
        return pg

    async def delete_page(self, shop_id: UUID, page_id: UUID) -> bool:
        if await self._get_shop_in_org(shop_id) is None:
            return False
        row = await self._session.get(StaticPageModel, page_id)
        if row is None or row.shop_id != shop_id:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True
