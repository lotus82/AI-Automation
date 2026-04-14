"""Витрины магазинов: CRUD, загрузка изображений, публичная витрина и темы мессенджеров."""

from __future__ import annotations

import logging
import re
import shutil
import uuid
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from sqlalchemy import and_, select, update as sa_update
from starlette.responses import FileResponse, Response

from src.api.dependencies import (
    AsyncSessionDep,
    MaxMessengerClientDep,
    SettingsDep,
    SettingsRepositoryDep,
)
from src.api.schemas.shops import (
    MessengerThemesPatch,
    ProductAdmin,
    ProductCreate,
    ProductPublic,
    ProductUpdate,
    PublicShopResponse,
    ShopAdminDetail,
    ShopCreate,
    ShopListItem,
    ShopOrderCreate,
    ShopOrderResponse,
    ShopUpdate,
    ThemeColors,
)
from src.infrastructure.services.shop_order_notify import (
    resolve_telegram_bot_token,
    send_max_order_message,
    send_telegram_order_message,
    send_vk_order_message,
)
from src.core.config import Settings
from src.infrastructure.models import ShopModel, ShopProductModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shops", tags=["shops"])

_MESSENGER_ORDER_LABELS: dict[str, str] = {"max": "MAX", "telegram": "Telegram", "vk": "VK"}

_MAX_UPLOAD = 5 * 1024 * 1024
_ALLOWED_EXT = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})

DEFAULT_MESSENGER_THEMES: dict[str, dict[str, str]] = {
    "max": {
        "accent": "#a78bfa",
        "bg": "#0f172a",
        "card": "#1e293b",
        "text": "#f8fafc",
        "muted": "#94a3b8",
    },
    "telegram": {
        "accent": "#229ed9",
        "bg": "#ffffff",
        "card": "#f4f4f5",
        "text": "#111827",
        "muted": "#6b7280",
    },
    "vk": {
        "accent": "#0077ff",
        "bg": "#edeef0",
        "card": "#ffffff",
        "text": "#000000",
        "muted": "#626d7a",
    },
}


def _shop_root(settings: Settings, shop_id: UUID) -> Path:
    return Path(settings.shop_upload_dir).resolve() / str(shop_id)


def _safe_join_under(root: Path, *parts: str) -> Path | None:
    target = (root / Path(*parts)).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    return target


def _ext_from_filename(name: str) -> str:
    suf = Path(name or "").suffix.lower()
    return suf if suf in _ALLOWED_EXT else ".jpg"


def _merge_themes(stored: dict[str, Any] | None, messenger: str) -> dict[str, str]:
    base = dict(DEFAULT_MESSENGER_THEMES.get(messenger, DEFAULT_MESSENGER_THEMES["max"]))
    raw = stored or {}
    custom = raw.get(messenger)
    if isinstance(custom, dict):
        for k, v in custom.items():
            if v is None or not isinstance(v, str):
                continue
            key = str(k).strip().lower()
            if key in base:
                base[key] = v.strip()
    return base


def _themes_patch_to_dict(patch: MessengerThemesPatch | None) -> dict[str, Any]:
    if patch is None:
        return {}
    out: dict[str, Any] = {}
    for key in ("max", "telegram", "vk"):
        tc: ThemeColors | None = getattr(patch, key, None)
        if tc is None:
            continue
        d = tc.model_dump(exclude_none=True)
        if d:
            out[key] = d
    return out


def _merge_stored_themes(existing: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing) if existing else {}
    for k, v in patch.items():
        if isinstance(v, dict):
            cur = dict(merged.get(k) or {}) if isinstance(merged.get(k), dict) else {}
            cur.update(v)
            merged[k] = cur
    return merged


def _public_file_url(request: Request, shop_id: UUID, relative: str) -> str:
    base = str(request.base_url).rstrip("/")
    rel = relative.lstrip("/").replace("\\", "/")
    return f"{base}/api/shops/assets/{shop_id}/{rel}"


def _slug_base_from_name(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")[:72]
    if s and re.match(r"^[a-z0-9]([a-z0-9-]{0,78}[a-z0-9])?$", s):
        return s
    return f"shop-{uuid.uuid4().hex[:10]}"


async def _unique_slug(session: AsyncSessionDep, base: str) -> str:
    candidate = base
    n = 0
    while True:
        ex = await session.scalar(select(ShopModel.id).where(ShopModel.slug == candidate))
        if ex is None:
            return candidate
        n += 1
        candidate = f"{base[:60]}-{n}"


def _decimal_price(p: Any) -> Decimal:
    if isinstance(p, Decimal):
        return p.quantize(Decimal("0.01"))
    return Decimal(str(p)).quantize(Decimal("0.01"))


def _strip_opt(s: str | None) -> str | None:
    t = (s or "").strip()
    return t or None


async def _shop_admin_detail(session: AsyncSessionDep, request: Request, shop_id: UUID) -> ShopAdminDetail:
    row = await session.get(ShopModel, shop_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Магазин не найден")
    logo = _public_file_url(request, row.id, row.logo_path) if row.logo_path else None
    return ShopAdminDetail(
        id=row.id,
        slug=row.slug,
        name=row.name,
        description=row.description or "",
        logo_url=logo,
        created_at=row.created_at,
        updated_at=row.updated_at,
        messenger_themes=dict(row.messenger_themes or {}),
        seller_max_chat_id=row.seller_max_chat_id,
        seller_telegram_chat_id=row.seller_telegram_chat_id,
        seller_vk_peer_id=row.seller_vk_peer_id,
    )


@router.post("/public/{slug}/order", response_model=ShopOrderResponse)
async def public_place_order(
    slug: str,
    body: ShopOrderCreate,
    session: AsyncSessionDep,
    settings: SettingsDep,
    settings_repo: SettingsRepositoryDep,
    max_client: MaxMessengerClientDep,
) -> ShopOrderResponse:
    """Оформление заказа: списание остатков и уведомление продавца в выбранном мессенджере."""
    s = (slug or "").strip().lower()
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Магазин не найден")
    shop = await session.scalar(select(ShopModel).where(ShopModel.slug == s))
    if shop is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Магазин не найден")

    m = (body.messenger or "max").strip().lower()
    if m not in DEFAULT_MESSENGER_THEMES:
        m = "max"

    buyer_contact = (body.buyer_contact or "").strip()
    if not buyer_contact:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Укажите контакт для связи")

    qty_by_pid: dict[UUID, int] = defaultdict(int)
    for it in body.items:
        qty_by_pid[it.product_id] += it.quantity

    p_result = await session.execute(
        select(ShopProductModel).where(
            ShopProductModel.shop_id == shop.id,
            ShopProductModel.id.in_(list(qty_by_pid.keys())),
        ),
    )
    found: dict[UUID, ShopProductModel] = {p.id: p for p in p_result.scalars().all()}
    if len(found) != len(qty_by_pid):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Один из товаров не найден в этом магазине")

    for pid, need in qty_by_pid.items():
        if found[pid].stock_quantity < need:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"Недостаточно товара «{found[pid].name}» на складе",
            )

    max_cid: int | None = None
    tg_chat: str | None = None
    tg_tok = ""
    vk_peer: int | None = None
    vk_tok = ""

    if m == "max":
        raw_sid = _strip_opt(shop.seller_max_chat_id)
        if not raw_sid:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Продавец не настроил получение заказов в MAX (chat id)",
            )
        try:
            max_cid = int(str(raw_sid).strip(), 10)
        except ValueError as e:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Некорректный chat id продавца MAX",
            ) from e
        if not (await max_client.resolve_bot_token()).strip():
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Бот MAX не настроен (MAX_BOT_TOKEN)",
            )
    elif m == "telegram":
        raw_sid = _strip_opt(shop.seller_telegram_chat_id)
        if not raw_sid:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Продавец не настроил chat id Telegram для заказов",
            )
        tg_chat = str(raw_sid).strip()
        tg_tok = (await resolve_telegram_bot_token(settings_repo, settings)).strip()
        if not tg_tok:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Бот Telegram не настроен (TELEGRAM_BOT_TOKEN)",
            )
    elif m == "vk":
        raw_sid = _strip_opt(shop.seller_vk_peer_id)
        if not raw_sid:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Продавец не настроил peer id VK для заказов",
            )
        try:
            vk_peer = int(str(raw_sid).strip(), 10)
        except ValueError as e:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Некорректный peer id продавца VK",
            ) from e
        vk_tok = (settings.vk_api_access_token or "").strip()
        if not vk_tok:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="VK_API_ACCESS_TOKEN не задан на сервере",
            )

    lines: list[str] = []
    total = Decimal("0")
    for pid in sorted(qty_by_pid.keys(), key=lambda x: str(x)):
        q = qty_by_pid[pid]
        pr = found[pid]
        price = _decimal_price(pr.price)
        sub = (price * Decimal(q)).quantize(Decimal("0.01"))
        total += sub
        lines.append(f"\u2014 {pr.name} \u00d7 {q} \u2014 {price:.2f} \u0440\u0443\u0431./\u0448\u0442, \u0441\u0443\u043c\u043c\u0430 {sub:.2f} \u0440\u0443\u0431.")

    ch_label = _MESSENGER_ORDER_LABELS.get(m, m)
    notify_text = (
        f"Новый заказ (витрина «{shop.name}»)\n"
        f"Канал: {ch_label}\n"
        f"Контакт покупателя: {buyer_contact}\n\n"
        + "\n".join(lines)
        + f"\n\n\u0418\u0442\u043e\u0433\u043e: {total:.2f} \u0440\u0443\u0431."
    )

    try:
        for pid, q in qty_by_pid.items():
            stmt = (
                sa_update(ShopProductModel)
                .where(
                    and_(
                        ShopProductModel.id == pid,
                        ShopProductModel.shop_id == shop.id,
                        ShopProductModel.stock_quantity >= q,
                    ),
                )
                .values(stock_quantity=ShopProductModel.stock_quantity - q)
            )
            res = await session.execute(stmt)
            if res.rowcount != 1:
                await session.rollback()
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail="Не удалось зарезервировать товар (остаток изменился). Обновите страницу.",
                )
        await session.commit()
    except HTTPException:
        raise

    async def _restore_stock() -> None:
        for pid, q in qty_by_pid.items():
            await session.execute(
                sa_update(ShopProductModel)
                .where(and_(ShopProductModel.id == pid, ShopProductModel.shop_id == shop.id))
                .values(stock_quantity=ShopProductModel.stock_quantity + q),
            )
        await session.commit()

    try:
        if m == "max" and max_cid is not None:
            await send_max_order_message(max_client, max_cid, notify_text)
        elif m == "telegram" and tg_chat:
            await send_telegram_order_message(tg_tok, tg_chat, notify_text)
        elif m == "vk" and vk_peer is not None:
            await send_vk_order_message(vk_tok, vk_peer, notify_text)
        else:
            raise RuntimeError(f"shop order: неизвестный канал m={m!r}")
    except Exception:
        logger.exception("shop order: не удалось отправить уведомление продавцу, slug=%s", s)
        try:
            await _restore_stock()
        except Exception:
            logger.exception("shop order: не удалось откатить остатки после сбоя отправки, slug=%s", s)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось отправить заказ продавцу. Попробуйте позже или свяжитесь с магазином напрямую.",
        ) from None

    return ShopOrderResponse()


@router.get("/assets/{shop_id}/{rest:path}")
async def get_shop_asset(shop_id: UUID, rest: str, settings: SettingsDep) -> FileResponse:
    if ".." in rest or rest.startswith(("/", "\\")):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Не найдено")
    root = _shop_root(settings, shop_id)
    path = _safe_join_under(root, *rest.split("/"))
    if path is None or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Не найдено")
    return FileResponse(path)


@router.get("/public/{slug}", response_model=PublicShopResponse)
async def public_shop_by_slug(
    slug: str,
    request: Request,
    session: AsyncSessionDep,
    messenger: str = "max",
) -> PublicShopResponse:
    m = (messenger or "max").strip().lower()
    if m not in DEFAULT_MESSENGER_THEMES:
        m = "max"
    row = await session.scalar(select(ShopModel).where(ShopModel.slug == slug.strip().lower()))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Магазин не найден")
    r = await session.execute(
        select(ShopProductModel)
        .where(ShopProductModel.shop_id == row.id)
        .order_by(ShopProductModel.sort_order, ShopProductModel.name),
    )
    products = r.scalars().all()
    theme = _merge_themes(dict(row.messenger_themes or {}), m)
    logo_url = _public_file_url(request, row.id, row.logo_path) if row.logo_path else None
    plist: list[ProductPublic] = []
    for p in products:
        photo = _public_file_url(request, row.id, p.photo_path) if p.photo_path else None
        price = _decimal_price(p.price)
        plist.append(
            ProductPublic(
                id=p.id,
                name=p.name,
                description=p.description or "",
                price=f"{price:.2f}",
                stock_quantity=int(p.stock_quantity or 0),
                photo_url=photo,
                sort_order=p.sort_order,
            ),
        )
    return PublicShopResponse(
        messenger=m,
        theme=theme,
        shop={
            "id": str(row.id),
            "slug": row.slug,
            "name": row.name,
            "description": row.description or "",
            "logo_url": logo_url,
        },
        products=plist,
    )


@router.get("", response_model=list[ShopListItem])
async def list_shops(session: AsyncSessionDep, request: Request) -> list[ShopListItem]:
    r = await session.execute(select(ShopModel).order_by(ShopModel.updated_at.desc()))
    rows = r.scalars().all()
    out: list[ShopListItem] = []
    for row in rows:
        logo = _public_file_url(request, row.id, row.logo_path) if row.logo_path else None
        out.append(
            ShopListItem(
                id=row.id,
                slug=row.slug,
                name=row.name,
                description=row.description or "",
                logo_url=logo,
                created_at=row.created_at,
                updated_at=row.updated_at,
            ),
        )
    return out


@router.post("", response_model=ShopAdminDetail, status_code=status.HTTP_201_CREATED)
async def create_shop(
    body: ShopCreate,
    session: AsyncSessionDep,
    request: Request,
    settings: SettingsDep,
) -> ShopAdminDetail:
    base = body.slug or _slug_base_from_name(body.name)
    slug = await _unique_slug(session, base)
    themes = _themes_patch_to_dict(body.messenger_themes)
    row = ShopModel(
        slug=slug,
        name=body.name.strip(),
        description=(body.description or "").strip(),
        messenger_themes=themes,
        seller_max_chat_id=_strip_opt(body.seller_max_chat_id),
        seller_telegram_chat_id=_strip_opt(body.seller_telegram_chat_id),
        seller_vk_peer_id=_strip_opt(body.seller_vk_peer_id),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    _shop_root(settings, row.id).mkdir(parents=True, exist_ok=True)
    return await _shop_admin_detail(session, request, row.id)


@router.get("/{shop_id}", response_model=ShopAdminDetail)
async def get_shop(shop_id: UUID, session: AsyncSessionDep, request: Request) -> ShopAdminDetail:
    return await _shop_admin_detail(session, request, shop_id)


@router.patch("/{shop_id}", response_model=ShopAdminDetail)
async def patch_shop(
    shop_id: UUID,
    body: ShopUpdate,
    session: AsyncSessionDep,
    request: Request,
) -> ShopAdminDetail:
    row = await session.get(ShopModel, shop_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Магазин не найден")
    if body.name is not None:
        row.name = body.name.strip()
    if body.description is not None:
        row.description = body.description.strip()
    if body.slug is not None:
        other = await session.scalar(select(ShopModel.id).where(ShopModel.slug == body.slug, ShopModel.id != shop_id))
        if other is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Такой slug уже занят")
        row.slug = body.slug
    if body.messenger_themes is not None:
        patch = _themes_patch_to_dict(body.messenger_themes)
        row.messenger_themes = _merge_stored_themes(dict(row.messenger_themes or {}), patch)
    if "seller_max_chat_id" in body.model_fields_set:
        row.seller_max_chat_id = _strip_opt(body.seller_max_chat_id)
    if "seller_telegram_chat_id" in body.model_fields_set:
        row.seller_telegram_chat_id = _strip_opt(body.seller_telegram_chat_id)
    if "seller_vk_peer_id" in body.model_fields_set:
        row.seller_vk_peer_id = _strip_opt(body.seller_vk_peer_id)
    await session.commit()
    await session.refresh(row)
    return await _shop_admin_detail(session, request, shop_id)


@router.delete("/{shop_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shop(shop_id: UUID, session: AsyncSessionDep, settings: SettingsDep) -> Response:
    row = await session.get(ShopModel, shop_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Магазин не найден")
    await session.delete(row)
    await session.commit()
    root = _shop_root(settings, shop_id)
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _read_upload_limit(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > _MAX_UPLOAD:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Файл больше 5 МБ")
    return data


@router.post("/{shop_id}/logo", response_model=ShopAdminDetail)
async def upload_shop_logo(
    shop_id: UUID,
    session: AsyncSessionDep,
    request: Request,
    settings: SettingsDep,
    file: UploadFile = File(...),
) -> ShopAdminDetail:
    row = await session.get(ShopModel, shop_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Магазин не найден")
    raw = await _read_upload_limit(file)
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Пустой файл")
    ext = _ext_from_filename(file.filename or "")
    rel = f"logo{ext}"
    root = _shop_root(settings, shop_id)
    root.mkdir(parents=True, exist_ok=True)
    dest = root / rel
    dest.write_bytes(raw)
    row.logo_path = rel
    await session.commit()
    await session.refresh(row)
    return await _shop_admin_detail(session, request, shop_id)


@router.get("/{shop_id}/products", response_model=list[ProductAdmin])
async def list_products(shop_id: UUID, session: AsyncSessionDep, request: Request) -> list[ProductAdmin]:
    shop = await session.get(ShopModel, shop_id)
    if shop is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Магазин не найден")
    r = await session.execute(
        select(ShopProductModel)
        .where(ShopProductModel.shop_id == shop_id)
        .order_by(ShopProductModel.sort_order, ShopProductModel.name),
    )
    rows = r.scalars().all()
    out: list[ProductAdmin] = []
    for p in rows:
        photo = _public_file_url(request, shop_id, p.photo_path) if p.photo_path else None
        price = _decimal_price(p.price)
        out.append(
            ProductAdmin(
                id=p.id,
                name=p.name,
                description=p.description or "",
                price=f"{price:.2f}",
                stock_quantity=int(p.stock_quantity or 0),
                photo_url=photo,
                sort_order=p.sort_order,
                created_at=p.created_at,
            ),
        )
    return out


@router.post("/{shop_id}/products", response_model=ProductAdmin, status_code=status.HTTP_201_CREATED)
async def create_product(
    shop_id: UUID,
    body: ProductCreate,
    session: AsyncSessionDep,
    request: Request,
) -> ProductAdmin:
    shop = await session.get(ShopModel, shop_id)
    if shop is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Магазин не найден")
    price = _decimal_price(body.price)
    p = ShopProductModel(
        shop_id=shop_id,
        name=body.name.strip(),
        description=(body.description or "").strip(),
        price=price,
        stock_quantity=body.stock_quantity,
        sort_order=body.sort_order,
    )
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return ProductAdmin(
        id=p.id,
        name=p.name,
        description=p.description or "",
        price=f"{_decimal_price(p.price):.2f}",
        stock_quantity=int(p.stock_quantity or 0),
        photo_url=None,
        sort_order=p.sort_order,
        created_at=p.created_at,
    )


@router.patch("/{shop_id}/products/{product_id}", response_model=ProductAdmin)
async def patch_product(
    shop_id: UUID,
    product_id: UUID,
    body: ProductUpdate,
    session: AsyncSessionDep,
    request: Request,
) -> ProductAdmin:
    p = await session.get(ShopProductModel, product_id)
    if p is None or p.shop_id != shop_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Товар не найден")
    if body.name is not None:
        p.name = body.name.strip()
    if body.description is not None:
        p.description = body.description.strip()
    if body.price is not None:
        p.price = _decimal_price(body.price)
    if body.sort_order is not None:
        p.sort_order = body.sort_order
    if body.stock_quantity is not None:
        p.stock_quantity = body.stock_quantity
    await session.commit()
    await session.refresh(p)
    photo = _public_file_url(request, shop_id, p.photo_path) if p.photo_path else None
    return ProductAdmin(
        id=p.id,
        name=p.name,
        description=p.description or "",
        price=f"{_decimal_price(p.price):.2f}",
        stock_quantity=int(p.stock_quantity or 0),
        photo_url=photo,
        sort_order=p.sort_order,
        created_at=p.created_at,
    )


@router.delete("/{shop_id}/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    shop_id: UUID,
    product_id: UUID,
    session: AsyncSessionDep,
    settings: SettingsDep,
) -> Response:
    p = await session.get(ShopProductModel, product_id)
    if p is None or p.shop_id != shop_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Товар не найден")
    rel = p.photo_path
    await session.delete(p)
    await session.commit()
    if rel:
        path = _safe_join_under(_shop_root(settings, shop_id), *rel.split("/"))
        if path and path.is_file():
            path.unlink(missing_ok=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{shop_id}/products/{product_id}/photo", response_model=ProductAdmin)
async def upload_product_photo(
    shop_id: UUID,
    product_id: UUID,
    session: AsyncSessionDep,
    request: Request,
    settings: SettingsDep,
    file: UploadFile = File(...),
) -> ProductAdmin:
    p = await session.get(ShopProductModel, product_id)
    if p is None or p.shop_id != shop_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Товар не найден")
    raw = await _read_upload_limit(file)
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Пустой файл")
    ext = _ext_from_filename(file.filename or "")
    rel = f"products/{product_id}{ext}"
    root = _shop_root(settings, shop_id)
    (root / "products").mkdir(parents=True, exist_ok=True)
    dest = _safe_join_under(root, "products", f"{product_id}{ext}")
    if dest is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Некорректный путь")
    dest.write_bytes(raw)
    p.photo_path = rel
    await session.commit()
    await session.refresh(p)
    photo = _public_file_url(request, shop_id, p.photo_path) if p.photo_path else None
    return ProductAdmin(
        id=p.id,
        name=p.name,
        description=p.description or "",
        price=f"{_decimal_price(p.price):.2f}",
        stock_quantity=int(p.stock_quantity or 0),
        photo_url=photo,
        sort_order=p.sort_order,
        created_at=p.created_at,
    )