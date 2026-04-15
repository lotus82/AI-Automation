"""Схемы публичной витрины /store (без JWT)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PublicStoreCategoryOut(BaseModel):
    id: UUID
    parent_id: UUID | None
    name: str
    order_index: int


class PublicStoreProductOut(BaseModel):
    id: UUID
    name: str
    description: str
    price: str
    stock_quantity: int
    photo_url: str | None
    photo_urls: list[str] = Field(default_factory=list)
    category_id: UUID | None = None
    tag: str | None = None
    sort_order: int


class PublicStoreShopOut(BaseModel):
    id: str
    slug: str
    name: str
    description: str
    logo_url: str | None = None


class PublicStoreCatalogResponse(BaseModel):
    messenger: str
    theme: dict[str, str]
    shop: PublicStoreShopOut
    categories: list[PublicStoreCategoryOut]
    products: list[PublicStoreProductOut]


class PublicStoreOrderItemIn(BaseModel):
    product_id: UUID
    quantity: int = Field(..., ge=1, le=9999)


class PublicStoreOrderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    phone: str = Field(..., min_length=1, max_length=64)
    address: str = Field(default="", max_length=2000)
    items: list[PublicStoreOrderItemIn] = Field(..., min_length=1)
    """Опционально: max | telegram | vk — отправить продавцу уведомление, если настроено."""
    messenger: str | None = Field(default=None, max_length=16)


class PublicStoreOrderResponse(BaseModel):
    ok: bool = True
    order_id: UUID
    message: str = "Заказ принят. С вами свяжутся для подтверждения."
