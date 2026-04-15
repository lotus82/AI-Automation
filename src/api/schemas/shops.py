"""Схемы API витрин магазинов."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

_SLUG_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,78}[a-z0-9])?$")
_PAGE_SLUG_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,158}[a-z0-9])?$")

MessengerKey = Literal["max", "telegram", "vk"]


class ThemeColors(BaseModel):
    """Перекрытия цветов темы под мессенджер (опционально)."""

    accent: str | None = None
    bg: str | None = None
    card: str | None = None
    text: str | None = None
    muted: str | None = None


class MessengerThemesPatch(BaseModel):
    """Частичные темы по ключам max / telegram / vk."""

    max: ThemeColors | None = None
    telegram: ThemeColors | None = None
    vk: ThemeColors | None = None


class ShopCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=512)
    description: str = ""
    slug: str | None = Field(default=None, max_length=80)
    """Опционально: привязка к организации (супер-админ); иначе — из контекста ``/shops/organization``."""
    organization_id: UUID | None = Field(default=None)
    messenger_themes: MessengerThemesPatch | None = None
    seller_max_chat_id: str | None = Field(default=None, max_length=64)
    seller_telegram_chat_id: str | None = Field(default=None, max_length=64)
    seller_vk_peer_id: str | None = Field(default=None, max_length=64)

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str | None) -> str | None:
        if v is None or not str(v).strip():
            return None
        s = str(v).strip().lower()
        if not _SLUG_RE.match(s):
            raise ValueError("slug: только латиница, цифры и дефис (2–80 символов)")
        return s


class ShopUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=512)
    description: str | None = None
    slug: str | None = Field(default=None, max_length=80)
    messenger_themes: MessengerThemesPatch | None = None
    seller_max_chat_id: str | None = Field(default=None, max_length=64)
    seller_telegram_chat_id: str | None = Field(default=None, max_length=64)
    seller_vk_peer_id: str | None = Field(default=None, max_length=64)

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not str(v).strip():
            return None
        s = str(v).strip().lower()
        if not _SLUG_RE.match(s):
            raise ValueError("slug: только латиница, цифры и дефис")
        return s


class ShopListItem(BaseModel):
    id: UUID
    organization_id: UUID | None = None
    slug: str
    name: str
    description: str
    logo_url: str | None
    created_at: datetime
    updated_at: datetime


class ShopAdminDetail(ShopListItem):
    messenger_themes: dict[str, Any]
    seller_max_chat_id: str | None = None
    seller_telegram_chat_id: str | None = None
    seller_vk_peer_id: str | None = None


ProductTagLiteral = Literal["new", "sale", "hot"]


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=512)
    description: str = ""
    price: Decimal = Field(..., ge=Decimal("0"), max_digits=12, decimal_places=2)
    stock_quantity: int = Field(0, ge=0, le=999_999_999)
    sort_order: int = 0
    category_id: UUID | None = None
    tag: ProductTagLiteral | None = None
    is_active: bool = True


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=512)
    description: str | None = None
    price: Decimal | None = Field(default=None, ge=Decimal("0"), max_digits=12, decimal_places=2)
    stock_quantity: int | None = Field(default=None, ge=0, le=999_999_999)
    sort_order: int | None = None
    category_id: UUID | None = None
    tag: ProductTagLiteral | None = None
    is_active: bool | None = None


class ProductPublic(BaseModel):
    id: UUID
    name: str
    description: str
    price: str
    stock_quantity: int
    photo_url: str | None
    sort_order: int


class ProductAdmin(ProductPublic):
    created_at: datetime
    category_id: UUID | None = None
    tag: str | None = None
    is_active: bool = True
    photo_urls: list[str] = Field(default_factory=list)


class PublicShopResponse(BaseModel):
    messenger: str
    theme: dict[str, str]
    shop: dict[str, Any]
    products: list[ProductPublic]


class ShopOrderItemIn(BaseModel):
    product_id: UUID
    quantity: int = Field(..., ge=1, le=9999)


class ShopOrderCreate(BaseModel):
    messenger: str = "max"
    buyer_contact: str = Field(..., min_length=1, max_length=500)
    items: list[ShopOrderItemIn] = Field(..., min_length=1)


class ShopOrderResponse(BaseModel):
    ok: bool = True
    message: str = "Ваш заказ принят, с вами свяжется продавец."


class CategoryAdmin(BaseModel):
    id: UUID
    parent_id: UUID | None
    name: str
    description: str
    order_index: int


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=512)
    description: str = ""
    parent_id: UUID | None = None
    order_index: int = 0


class CategoryPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=512)
    description: str | None = None
    order_index: int | None = None


class StaticPageAdmin(BaseModel):
    id: UUID
    title: str
    slug: str
    content: str


class StaticPageCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    slug: str = Field(..., min_length=1, max_length=160)
    content: str = ""

    @field_validator("slug")
    @classmethod
    def _slug_page(cls, v: str) -> str:
        s = str(v).strip().lower()
        if not _PAGE_SLUG_RE.match(s):
            raise ValueError("slug: только латиница, цифры и дефис")
        return s


class StaticPagePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    slug: str | None = Field(default=None, min_length=1, max_length=160)
    content: str | None = None

    @field_validator("slug")
    @classmethod
    def _slug_page_patch(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = str(v).strip().lower()
        if not _PAGE_SLUG_RE.match(s):
            raise ValueError("slug: только латиница, цифры и дефис")
        return s


class DiscountAdmin(BaseModel):
    id: UUID
    name: str
    percentage: str
    start_date: date
    end_date: date


class DiscountCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=512)
    percentage: Decimal = Field(..., ge=Decimal("0"), le=Decimal("100"), max_digits=5, decimal_places=2)
    start_date: date
    end_date: date


class OrderItemAdmin(BaseModel):
    id: UUID
    product_id: UUID
    quantity: int
    price_at_time: str


class OrderAdmin(BaseModel):
    id: UUID
    status: str
    customer_info: dict[str, Any]
    total_amount: str
    delivery_address: str
    delivery_status: str
    items: list[OrderItemAdmin]
