"""Схемы API витрин магазинов."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

_SLUG_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,78}[a-z0-9])?$")

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


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=512)
    description: str = ""
    price: Decimal = Field(..., ge=Decimal("0"), max_digits=12, decimal_places=2)
    stock_quantity: int = Field(0, ge=0, le=999_999_999)
    sort_order: int = 0


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=512)
    description: str | None = None
    price: Decimal | None = Field(default=None, ge=Decimal("0"), max_digits=12, decimal_places=2)
    stock_quantity: int | None = Field(default=None, ge=0, le=999_999_999)
    sort_order: int | None = None


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
