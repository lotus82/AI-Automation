"""Публичная витрина: каталог и заказы по slug без авторизации."""

from __future__ import annotations

import logging
from collections import defaultdict
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import and_, select, update as sa_update

from src.api.dependencies import (
    AsyncSessionDep,
    MaxMessengerClientDep,
    SettingsDep,
    SettingsRepositoryDep,
)
from src.api.routers.shops import (
    DEFAULT_MESSENGER_THEMES,
    _MESSENGER_ORDER_LABELS,
    _decimal_price,
    _merge_themes,
    _public_file_url,
    _resolve_logo_url,
    _seller_from_settings,
    _shop_settings,
)
from src.api.schemas.public_store import (
    PublicStoreCatalogResponse,
    PublicStoreCategoryOut,
    PublicStoreOrderCreate,
    PublicStoreOrderResponse,
    PublicStoreProductOut,
    PublicStoreShopOut,
)
from src.infrastructure.models import (
    CategoryModel,
    OrderItemModel,
    OrderModel,
    ProductModel,
    ShopModel,
    ShopOrderStatus,
)
from src.infrastructure.services.shop_order_notify import (
    resolve_telegram_bot_token,
    send_max_order_message,
    send_telegram_order_message,
    send_vk_order_message,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/public-store", tags=["public-store"])


async def _one_shop_by_slug(session: AsyncSessionDep, slug: str) -> ShopModel:
    s = (slug or "").strip().lower()
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Магазин не найден")
    stmt = select(ShopModel).where(ShopModel.slug == s)
    matches = (await session.scalars(stmt)).all()
    if not matches:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Магазин не найден")
    if len(matches) > 1:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Несколько магазинов с таким адресом. Уточните ссылку у продавца.",
        )
    return matches[0]


def _product_photos_urls(request: Request, shop_id: UUID, photos: object | None) -> tuple[str | None, list[str]]:
    rels = photos if isinstance(photos, list) else []
    urls: list[str] = []
    for x in rels:
        if x is None:
            continue
        rel = str(x).strip()
        if not rel:
            continue
        urls.append(_public_file_url(request, shop_id, rel))
    primary = urls[0] if urls else None
    return primary, urls


@router.get("/{shop_slug}", response_model=PublicStoreCatalogResponse)
async def public_store_catalog(
    shop_slug: str,
    request: Request,
    session: AsyncSessionDep,
    messenger: str = Query("max", description="Тема оформления: max | telegram | vk"),
) -> PublicStoreCatalogResponse:
    m = (messenger or "max").strip().lower()
    if m not in DEFAULT_MESSENGER_THEMES:
        m = "max"
    row = await _one_shop_by_slug(session, shop_slug)
    st = _shop_settings(row)
    mt = st.get("messenger_themes")
    theme = _merge_themes(dict(mt) if isinstance(mt, dict) else {}, m)
    logo_url = _resolve_logo_url(request, row)

    cat_rows = (
        await session.scalars(
            select(CategoryModel)
            .where(CategoryModel.shop_id == row.id)
            .order_by(CategoryModel.order_index, CategoryModel.name),
        )
    ).all()
    categories = [
        PublicStoreCategoryOut(
            id=c.id,
            parent_id=c.parent_id,
            name=c.name,
            order_index=c.order_index,
        )
        for c in cat_rows
    ]

    p_rows = (
        await session.scalars(
            select(ProductModel)
            .where(ProductModel.shop_id == row.id, ProductModel.is_active.is_(True))
            .order_by(ProductModel.sort_order, ProductModel.name),
        )
    ).all()
    products: list[PublicStoreProductOut] = []
    for p in p_rows:
        primary, photo_urls = _product_photos_urls(request, row.id, p.photos)
        price = _decimal_price(p.price)
        tag_val = p.tag.value if p.tag is not None else None
        products.append(
            PublicStoreProductOut(
                id=p.id,
                name=p.name,
                description=p.description or "",
                price=f"{price:.2f}",
                stock_quantity=int(p.stock_quantity or 0),
                photo_url=primary,
                photo_urls=photo_urls if photo_urls else ([primary] if primary else []),
                category_id=p.category_id,
                tag=tag_val,
                sort_order=p.sort_order,
            ),
        )

    return PublicStoreCatalogResponse(
        messenger=m,
        theme=theme,
        shop=PublicStoreShopOut(
            id=str(row.id),
            slug=row.slug,
            name=row.name,
            description=row.description or "",
            logo_url=logo_url,
        ),
        categories=categories,
        products=products,
    )


@router.post("/{shop_slug}/orders", response_model=PublicStoreOrderResponse)
async def public_store_create_order(
    shop_slug: str,
    body: PublicStoreOrderCreate,
    session: AsyncSessionDep,
    settings: SettingsDep,
    settings_repo: SettingsRepositoryDep,
    max_client: MaxMessengerClientDep,
) -> PublicStoreOrderResponse:
    """Создаёт заказ в БД, списывает остатки; уведомление продавцу — опционально (``messenger``)."""
    shop = await _one_shop_by_slug(session, shop_slug)
    name = body.name.strip()
    phone = body.phone.strip()
    address = (body.address or "").strip()
    if not name or not phone:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Укажите имя и телефон")

    qty_by_pid: dict[UUID, int] = defaultdict(int)
    for it in body.items:
        qty_by_pid[it.product_id] += it.quantity

    p_result = await session.execute(
        select(ProductModel).where(
            ProductModel.shop_id == shop.id,
            ProductModel.id.in_(list(qty_by_pid.keys())),
            ProductModel.is_active.is_(True),
        ),
    )
    found: dict[UUID, ProductModel] = {p.id: p for p in p_result.scalars().all()}
    if len(found) != len(qty_by_pid):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Один из товаров не найден или снят с продажи")

    for pid, need in qty_by_pid.items():
        if found[pid].stock_quantity < need:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"Недостаточно товара «{found[pid].name}» на складе",
            )

    lines: list[str] = []
    total = Decimal("0")
    for pid in sorted(qty_by_pid.keys(), key=lambda x: str(x)):
        q = qty_by_pid[pid]
        pr = found[pid]
        price = _decimal_price(pr.price)
        sub = (price * Decimal(q)).quantize(Decimal("0.01"))
        total += sub
        lines.append(
            f"\u2014 {pr.name} \u00d7 {q} \u2014 {price:.2f} \u0440\u0443\u0431./\u0448\u0442, "
            f"\u0441\u0443\u043c\u043c\u0430 {sub:.2f} \u0440\u0443\u0431.",
        )

    notify_m = (body.messenger or "").strip().lower()
    if notify_m in ("", "none", "off"):
        notify_m = ""

    order_id: UUID | None = None
    try:
        for pid, q in qty_by_pid.items():
            stmt = (
                sa_update(ProductModel)
                .where(
                    and_(
                        ProductModel.id == pid,
                        ProductModel.shop_id == shop.id,
                        ProductModel.stock_quantity >= q,
                    ),
                )
                .values(stock_quantity=ProductModel.stock_quantity - q)
            )
            res = await session.execute(stmt)
            if res.rowcount != 1:
                await session.rollback()
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail="Не удалось зарезервировать товар. Обновите страницу и попробуйте снова.",
                )

        customer_info: dict[str, Any] = {
            "name": name,
            "phone": phone,
            "address": address,
            "source": "public_store",
        }
        order = OrderModel(
            shop_id=shop.id,
            status=ShopOrderStatus.new,
            customer_info=customer_info,
            total_amount=total,
            delivery_address=address,
            delivery_status="new",
        )
        session.add(order)
        await session.flush()
        for pid, q in qty_by_pid.items():
            pr = found[pid]
            session.add(
                OrderItemModel(
                    order_id=order.id,
                    product_id=pid,
                    quantity=q,
                    price_at_time=_decimal_price(pr.price),
                ),
            )
        order_id = order.id
        await session.commit()
    except HTTPException:
        raise
    except Exception:
        logger.exception("public_store: ошибка создания заказа slug=%s", shop_slug)
        await session.rollback()
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось оформить заказ. Попробуйте позже.",
        ) from None

    assert order_id is not None

    ch_label = "витрина /store"
    notify_text = (
        f"Новый заказ (витрина «{shop.name}»)\n"
        f"Канал: {ch_label}\n"
        f"Имя: {name}\nТелефон: {phone}\nАдрес: {address or '\u2014'}\n\n"
        + "\n".join(lines)
        + f"\n\n\u0418\u0442\u043e\u0433\u043e: {total:.2f} \u0440\u0443\u0431."
    )

    if notify_m and notify_m in DEFAULT_MESSENGER_THEMES:
        m = notify_m
        max_cid: int | None = None
        tg_chat: str | None = None
        tg_tok = ""
        vk_peer: int | None = None
        vk_tok = ""
        try:
            if m == "max":
                raw_sid = _seller_from_settings(shop, "seller_max_chat_id")
                if raw_sid and (await max_client.resolve_bot_token()).strip():
                    max_cid = int(str(raw_sid).strip(), 10)
                    await send_max_order_message(max_client, max_cid, notify_text)
            elif m == "telegram":
                raw_sid = _seller_from_settings(shop, "seller_telegram_chat_id")
                if raw_sid:
                    tg_chat = str(raw_sid).strip()
                    tg_tok = (await resolve_telegram_bot_token(settings_repo, settings)).strip()
                    if tg_tok:
                        await send_telegram_order_message(tg_tok, tg_chat, notify_text)
            elif m == "vk":
                raw_sid = _seller_from_settings(shop, "seller_vk_peer_id")
                vk_tok = (settings.vk_api_access_token or "").strip()
                if raw_sid and vk_tok:
                    vk_peer = int(str(raw_sid).strip(), 10)
                    await send_vk_order_message(vk_tok, vk_peer, notify_text)
        except Exception:
            ch = _MESSENGER_ORDER_LABELS.get(m, m)
            logger.warning(
                "public_store: не удалось отправить уведомление в %s, заказ %s сохранён",
                ch,
                order_id,
                exc_info=True,
            )

    return PublicStoreOrderResponse(order_id=order_id)
