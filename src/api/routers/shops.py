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

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import and_, select, update as sa_update
from sqlalchemy.exc import IntegrityError
from starlette.responses import FileResponse, Response

from src.api.dependencies import (
    AsyncSessionDep,
    MaxMessengerClientDep,
    SettingsDep,
    SettingsRepositoryDep,
)
from src.api.dependencies_portal import PortalUserDep
from src.api.org_scope import resolve_organization_scope
from src.infrastructure.repositories.shop_repositories import (
    SqlAlchemyCategoryRepository,
    SqlAlchemyDiscountRepository,
    SqlAlchemyShopOrderRepository,
    SqlAlchemyShopRepository,
    SqlAlchemyStaticPageRepository,
)
from src.api.schemas.shops import (
    CategoryAdmin,
    CategoryCreate,
    CategoryPatch,
    DiscountAdmin,
    DiscountCreate,
    MessengerThemesPatch,
    OrderAdmin,
    OrderItemAdmin,
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
    StaticPageAdmin,
    StaticPageCreate,
    StaticPagePatch,
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
from src.infrastructure.models import ProductModel, ShopModel, ShopProductTag

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


def _shop_settings(row: ShopModel) -> dict[str, Any]:
    return dict(row.settings or {})


def _row_logo_upload_rel(row: ShopModel) -> str | None:
    raw = _shop_settings(row).get("upload_logo_rel")
    if raw is None:
        return None
    s = str(raw).strip()
    return s or None


def _resolve_logo_url(request: Request, row: ShopModel) -> str | None:
    if row.logo_url and str(row.logo_url).strip():
        return str(row.logo_url).strip()
    rel = _row_logo_upload_rel(row)
    if rel:
        return _public_file_url(request, row.id, rel)
    return None


def _seller_from_settings(row: ShopModel, key: str) -> str | None:
    raw = _shop_settings(row).get(key)
    if raw is None:
        return None
    return _strip_opt(str(raw))


def _product_primary_photo_rel(photos: object | None) -> str | None:
    if not isinstance(photos, list) or not photos:
        return None
    p0 = photos[0]
    if p0 is None:
        return None
    s = str(p0).strip()
    return s or None


def _product_to_admin(request: Request, shop_id: UUID, p: ProductModel) -> ProductAdmin:
    rels = p.photos if isinstance(p.photos, list) else []
    photo_urls: list[str] = []
    for x in rels:
        if x is None:
            continue
        s = str(x).strip()
        if not s:
            continue
        photo_urls.append(_public_file_url(request, shop_id, s))
    primary = photo_urls[0] if photo_urls else None
    price = _decimal_price(p.price)
    tag_val = p.tag.value if p.tag is not None else None
    return ProductAdmin(
        id=p.id,
        name=p.name,
        description=p.description or "",
        price=f"{price:.2f}",
        stock_quantity=int(p.stock_quantity or 0),
        photo_url=primary,
        sort_order=p.sort_order,
        created_at=p.created_at,
        category_id=p.category_id,
        tag=tag_val,
        is_active=bool(p.is_active),
        photo_urls=photo_urls,
    )


def _slug_base_from_name(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")[:72]
    if s and re.match(r"^[a-z0-9]([a-z0-9-]{0,78}[a-z0-9])?$", s):
        return s
    return f"shop-{uuid.uuid4().hex[:10]}"


async def _unique_slug(session: AsyncSessionDep, base: str, organization_id: UUID | None) -> str:
    candidate = base
    n = 0
    while True:
        org_clause = (
            ShopModel.organization_id.is_(None)
            if organization_id is None
            else ShopModel.organization_id == organization_id
        )
        ex = await session.scalar(select(ShopModel.id).where(ShopModel.slug == candidate, org_clause))
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
    logo = _resolve_logo_url(request, row)
    st = _shop_settings(row)
    mt = st.get("messenger_themes")
    themes = dict(mt) if isinstance(mt, dict) else {}
    return ShopAdminDetail(
        id=row.id,
        organization_id=row.organization_id,
        slug=row.slug,
        name=row.name,
        description=row.description or "",
        logo_url=logo,
        created_at=row.created_at,
        updated_at=row.updated_at,
        messenger_themes=themes,
        seller_max_chat_id=_seller_from_settings(row, "seller_max_chat_id"),
        seller_telegram_chat_id=_seller_from_settings(row, "seller_telegram_chat_id"),
        seller_vk_peer_id=_seller_from_settings(row, "seller_vk_peer_id"),
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
    stmt = select(ShopModel).where(ShopModel.slug == s)
    matches = (await session.scalars(stmt)).all()
    if not matches:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Магазин не найден")
    if len(matches) > 1:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Несколько магазинов с таким адресом. Используйте ссылку с явным идентификатором магазина.",
        )
    shop = matches[0]

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
        select(ProductModel).where(
            ProductModel.shop_id == shop.id,
            ProductModel.id.in_(list(qty_by_pid.keys())),
        ),
    )
    found: dict[UUID, ProductModel] = {p.id: p for p in p_result.scalars().all()}
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
        raw_sid = _seller_from_settings(shop, "seller_max_chat_id")
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
        raw_sid = _seller_from_settings(shop, "seller_telegram_chat_id")
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
        raw_sid = _seller_from_settings(shop, "seller_vk_peer_id")
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
                    detail="Не удалось зарезервировать товар (остаток изменился). Обновите страницу.",
                )
        await session.commit()
    except HTTPException:
        raise

    async def _restore_stock() -> None:
        for pid, q in qty_by_pid.items():
            await session.execute(
                sa_update(ProductModel)
                .where(and_(ProductModel.id == pid, ProductModel.shop_id == shop.id))
                .values(stock_quantity=ProductModel.stock_quantity + q),
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
    s_slug = slug.strip().lower()
    stmt = select(ShopModel).where(ShopModel.slug == s_slug)
    matches = (await session.scalars(stmt)).all()
    if not matches:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Магазин не найден")
    if len(matches) > 1:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Несколько магазинов с таким адресом. Используйте ссылку с id магазина.",
        )
    row = matches[0]
    r = await session.execute(
        select(ProductModel)
        .where(ProductModel.shop_id == row.id, ProductModel.is_active.is_(True))
        .order_by(ProductModel.sort_order, ProductModel.name),
    )
    products = r.scalars().all()
    st = _shop_settings(row)
    mt = st.get("messenger_themes")
    theme = _merge_themes(dict(mt) if isinstance(mt, dict) else {}, m)
    logo_url = _resolve_logo_url(request, row)
    plist: list[ProductPublic] = []
    for p in products:
        rel = _product_primary_photo_rel(p.photos)
        photo = _public_file_url(request, row.id, rel) if rel else None
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
        logo = _resolve_logo_url(request, row)
        out.append(
            ShopListItem(
                id=row.id,
                organization_id=row.organization_id,
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
    slug = await _unique_slug(session, base, body.organization_id)
    patch = _themes_patch_to_dict(body.messenger_themes)
    settings: dict[str, Any] = {
        "messenger_themes": _merge_stored_themes({}, patch) if patch else {},
    }
    for fld in ("seller_max_chat_id", "seller_telegram_chat_id", "seller_vk_peer_id"):
        v = getattr(body, fld, None)
        if v is not None:
            settings[fld] = _strip_opt(str(v))
    row = ShopModel(
        organization_id=body.organization_id,
        slug=slug,
        name=body.name.strip(),
        description=(body.description or "").strip(),
        settings=settings,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    _shop_root(settings, row.id).mkdir(parents=True, exist_ok=True)
    return await _shop_admin_detail(session, request, row.id)


@router.get("/organization", response_model=list[ShopListItem])
async def list_shops_by_organization(
    user: PortalUserDep,
    session: AsyncSessionDep,
    request: Request,
    organization_id: UUID | None = Query(
        None,
        description="Супер-админ: id организации; без параметра — магазины без привязки к организации",
    ),
) -> list[ShopListItem]:
    """Список магазинов в области текущего тенанта (JWT + ``resolve_organization_scope``)."""
    scope = resolve_organization_scope(user, organization_id)
    repo = SqlAlchemyShopRepository(session, organization_id=scope)
    rows = await repo.list_shops()
    out: list[ShopListItem] = []
    for row in rows:
        logo = _resolve_logo_url(request, row)
        out.append(
            ShopListItem(
                id=row.id,
                organization_id=row.organization_id,
                slug=row.slug,
                name=row.name,
                description=row.description or "",
                logo_url=logo,
                created_at=row.created_at,
                updated_at=row.updated_at,
            ),
        )
    return out


@router.post("/organization", response_model=ShopAdminDetail, status_code=status.HTTP_201_CREATED)
async def create_shop_by_organization(
    user: PortalUserDep,
    body: ShopCreate,
    session: AsyncSessionDep,
    request: Request,
    settings: SettingsDep,
    organization_id: UUID | None = Query(
        None,
        description="Супер-админ: id организации; иначе берётся из JWT / тела",
    ),
) -> ShopAdminDetail:
    """Создание магазина в организации (или без организации, если супер-админ не передал scope)."""
    oid_q = organization_id if organization_id is not None else body.organization_id
    scope = resolve_organization_scope(user, oid_q)
    base = body.slug or _slug_base_from_name(body.name)
    slug = await _unique_slug(session, base, scope)
    patch = _themes_patch_to_dict(body.messenger_themes)
    settings_dict: dict[str, Any] = {
        "messenger_themes": _merge_stored_themes({}, patch) if patch else {},
    }
    for fld in ("seller_max_chat_id", "seller_telegram_chat_id", "seller_vk_peer_id"):
        v = getattr(body, fld, None)
        if v is not None:
            settings_dict[fld] = _strip_opt(str(v))
    row = ShopModel(
        organization_id=scope,
        slug=slug,
        name=body.name.strip(),
        description=(body.description or "").strip(),
        settings=settings_dict,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    _shop_root(settings, row.id).mkdir(parents=True, exist_ok=True)
    return await _shop_admin_detail(session, request, row.id)


# --- Админ: категории, статические страницы, скидки, заказы (JWT + organization_id в query) ---


@router.get("/{shop_id}/categories", response_model=list[CategoryAdmin])
async def admin_list_categories(
    shop_id: UUID,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(None),
) -> list[CategoryAdmin]:
    scope = resolve_organization_scope(user, organization_id)
    repo = SqlAlchemyCategoryRepository(session, organization_id=scope)
    rows = await repo.list_categories(shop_id)
    return [
        CategoryAdmin(
            id=r.id,
            parent_id=r.parent_id,
            name=r.name,
            description=r.description or "",
            order_index=r.order_index,
        )
        for r in rows
    ]


@router.post("/{shop_id}/categories", response_model=CategoryAdmin, status_code=status.HTTP_201_CREATED)
async def admin_create_category(
    shop_id: UUID,
    body: CategoryCreate,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(None),
) -> CategoryAdmin:
    scope = resolve_organization_scope(user, organization_id)
    repo = SqlAlchemyCategoryRepository(session, organization_id=scope)
    row = await repo.create_category(
        shop_id,
        name=body.name,
        description=body.description,
        parent_id=body.parent_id,
        order_index=body.order_index,
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Магазин не найден или нет доступа")
    await session.commit()
    await session.refresh(row)
    return CategoryAdmin(
        id=row.id,
        parent_id=row.parent_id,
        name=row.name,
        description=row.description or "",
        order_index=row.order_index,
    )


@router.patch("/{shop_id}/categories/{category_id}", response_model=CategoryAdmin)
async def admin_patch_category(
    shop_id: UUID,
    category_id: UUID,
    body: CategoryPatch,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(None),
) -> CategoryAdmin:
    scope = resolve_organization_scope(user, organization_id)
    repo = SqlAlchemyCategoryRepository(session, organization_id=scope)
    row = await repo.update_category(
        shop_id,
        category_id,
        name=body.name,
        description=body.description,
        order_index=body.order_index,
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Категория не найдена")
    await session.commit()
    await session.refresh(row)
    return CategoryAdmin(
        id=row.id,
        parent_id=row.parent_id,
        name=row.name,
        description=row.description or "",
        order_index=row.order_index,
    )


@router.delete("/{shop_id}/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_category(
    shop_id: UUID,
    category_id: UUID,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(None),
) -> Response:
    scope = resolve_organization_scope(user, organization_id)
    repo = SqlAlchemyCategoryRepository(session, organization_id=scope)
    ok = await repo.delete_category(shop_id, category_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Категория не найдена")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{shop_id}/static-pages", response_model=list[StaticPageAdmin])
async def admin_list_static_pages(
    shop_id: UUID,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(None),
) -> list[StaticPageAdmin]:
    scope = resolve_organization_scope(user, organization_id)
    repo = SqlAlchemyStaticPageRepository(session, organization_id=scope)
    rows = await repo.list_pages(shop_id)
    return [StaticPageAdmin(id=r.id, title=r.title, slug=r.slug, content=r.content or "") for r in rows]


@router.post("/{shop_id}/static-pages", response_model=StaticPageAdmin, status_code=status.HTTP_201_CREATED)
async def admin_create_static_page(
    shop_id: UUID,
    body: StaticPageCreate,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(None),
) -> StaticPageAdmin:
    scope = resolve_organization_scope(user, organization_id)
    repo = SqlAlchemyStaticPageRepository(session, organization_id=scope)
    row = await repo.create_page(shop_id, title=body.title, slug=body.slug, content=body.content)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Магазин не найден или нет доступа")
    try:
        await session.commit()
        await session.refresh(row)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Страница с таким slug уже есть") from None
    return StaticPageAdmin(id=row.id, title=row.title, slug=row.slug, content=row.content or "")


@router.patch("/{shop_id}/static-pages/{page_id}", response_model=StaticPageAdmin)
async def admin_patch_static_page(
    shop_id: UUID,
    page_id: UUID,
    body: StaticPagePatch,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(None),
) -> StaticPageAdmin:
    scope = resolve_organization_scope(user, organization_id)
    repo = SqlAlchemyStaticPageRepository(session, organization_id=scope)
    row = await repo.update_page(
        shop_id,
        page_id,
        title=body.title,
        slug=body.slug,
        content=body.content,
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Страница не найдена или slug занят")
    try:
        await session.commit()
        await session.refresh(row)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Конфликт slug") from None
    return StaticPageAdmin(id=row.id, title=row.title, slug=row.slug, content=row.content or "")


@router.delete("/{shop_id}/static-pages/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_static_page(
    shop_id: UUID,
    page_id: UUID,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(None),
) -> Response:
    scope = resolve_organization_scope(user, organization_id)
    repo = SqlAlchemyStaticPageRepository(session, organization_id=scope)
    ok = await repo.delete_page(shop_id, page_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Страница не найдена")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{shop_id}/discounts", response_model=list[DiscountAdmin])
async def admin_list_discounts(
    shop_id: UUID,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(None),
) -> list[DiscountAdmin]:
    scope = resolve_organization_scope(user, organization_id)
    repo = SqlAlchemyDiscountRepository(session, organization_id=scope)
    rows = await repo.list_discounts(shop_id)
    out: list[DiscountAdmin] = []
    for r in rows:
        pct = _decimal_price(r.percentage)
        out.append(
            DiscountAdmin(
                id=r.id,
                name=r.name,
                percentage=f"{pct:.2f}",
                start_date=r.start_date,
                end_date=r.end_date,
            ),
        )
    return out


@router.post("/{shop_id}/discounts", response_model=DiscountAdmin, status_code=status.HTTP_201_CREATED)
async def admin_create_discount(
    shop_id: UUID,
    body: DiscountCreate,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(None),
) -> DiscountAdmin:
    scope = resolve_organization_scope(user, organization_id)
    repo = SqlAlchemyDiscountRepository(session, organization_id=scope)
    row = await repo.create_discount(
        shop_id,
        name=body.name,
        percentage=body.percentage,
        start_date=body.start_date,
        end_date=body.end_date,
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Магазин не найден или нет доступа")
    await session.commit()
    await session.refresh(row)
    pct = _decimal_price(row.percentage)
    return DiscountAdmin(
        id=row.id,
        name=row.name,
        percentage=f"{pct:.2f}",
        start_date=row.start_date,
        end_date=row.end_date,
    )


@router.delete("/{shop_id}/discounts/{discount_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_discount(
    shop_id: UUID,
    discount_id: UUID,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(None),
) -> Response:
    scope = resolve_organization_scope(user, organization_id)
    repo = SqlAlchemyDiscountRepository(session, organization_id=scope)
    ok = await repo.delete_discount(shop_id, discount_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Скидка не найдена")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{shop_id}/orders", response_model=list[OrderAdmin])
async def admin_list_orders(
    shop_id: UUID,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(None),
) -> list[OrderAdmin]:
    scope = resolve_organization_scope(user, organization_id)
    repo = SqlAlchemyShopOrderRepository(session, organization_id=scope)
    rows = await repo.list_orders_with_items(shop_id)
    out: list[OrderAdmin] = []
    for o in rows:
        items_out = [
            OrderItemAdmin(
                id=it.id,
                product_id=it.product_id,
                quantity=it.quantity,
                price_at_time=f"{_decimal_price(it.price_at_time):.2f}",
            )
            for it in (o.items or [])
        ]
        out.append(
            OrderAdmin(
                id=o.id,
                status=o.status.value if hasattr(o.status, "value") else str(o.status),
                customer_info=dict(o.customer_info or {}),
                total_amount=f"{_decimal_price(o.total_amount):.2f}",
                delivery_address=o.delivery_address or "",
                delivery_status=o.delivery_status or "",
                items=items_out,
            ),
        )
    return out


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
        org_clause = (
            ShopModel.organization_id.is_(None)
            if row.organization_id is None
            else ShopModel.organization_id == row.organization_id
        )
        other = await session.scalar(
            select(ShopModel.id).where(
                ShopModel.slug == body.slug,
                ShopModel.id != shop_id,
                org_clause,
            ),
        )
        if other is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Такой slug уже занят")
        row.slug = body.slug
    st = dict(row.settings or {})
    if body.messenger_themes is not None:
        patch = _themes_patch_to_dict(body.messenger_themes)
        st["messenger_themes"] = _merge_stored_themes(dict(st.get("messenger_themes") or {}), patch)
    if "seller_max_chat_id" in body.model_fields_set:
        st["seller_max_chat_id"] = _strip_opt(body.seller_max_chat_id)
    if "seller_telegram_chat_id" in body.model_fields_set:
        st["seller_telegram_chat_id"] = _strip_opt(body.seller_telegram_chat_id)
    if "seller_vk_peer_id" in body.model_fields_set:
        st["seller_vk_peer_id"] = _strip_opt(body.seller_vk_peer_id)
    row.settings = st
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
    st = dict(row.settings or {})
    st["upload_logo_rel"] = rel
    row.settings = st
    await session.commit()
    await session.refresh(row)
    return await _shop_admin_detail(session, request, shop_id)


@router.get("/{shop_id}/products", response_model=list[ProductAdmin])
async def list_products(shop_id: UUID, session: AsyncSessionDep, request: Request) -> list[ProductAdmin]:
    shop = await session.get(ShopModel, shop_id)
    if shop is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Магазин не найден")
    r = await session.execute(
        select(ProductModel)
        .where(ProductModel.shop_id == shop_id)
        .order_by(ProductModel.sort_order, ProductModel.name),
    )
    rows = r.scalars().all()
    return [_product_to_admin(request, shop_id, p) for p in rows]


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
    tag_enum: ShopProductTag | None = None
    if body.tag is not None:
        tag_enum = ShopProductTag(body.tag)
    p = ProductModel(
        shop_id=shop_id,
        category_id=body.category_id,
        name=body.name.strip(),
        description=(body.description or "").strip(),
        price=price,
        stock_quantity=body.stock_quantity,
        sort_order=body.sort_order,
        photos=[],
        is_active=body.is_active,
        tag=tag_enum,
    )
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return _product_to_admin(request, shop_id, p)


@router.patch("/{shop_id}/products/{product_id}", response_model=ProductAdmin)
async def patch_product(
    shop_id: UUID,
    product_id: UUID,
    body: ProductUpdate,
    session: AsyncSessionDep,
    request: Request,
) -> ProductAdmin:
    p = await session.get(ProductModel, product_id)
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
    if "category_id" in body.model_fields_set:
        p.category_id = body.category_id
    if "tag" in body.model_fields_set:
        p.tag = ShopProductTag(body.tag) if body.tag is not None else None
    if "is_active" in body.model_fields_set and body.is_active is not None:
        p.is_active = body.is_active
    await session.commit()
    await session.refresh(p)
    return _product_to_admin(request, shop_id, p)


@router.delete("/{shop_id}/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    shop_id: UUID,
    product_id: UUID,
    session: AsyncSessionDep,
    settings: SettingsDep,
) -> Response:
    p = await session.get(ProductModel, product_id)
    if p is None or p.shop_id != shop_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Товар не найден")
    rel = _product_primary_photo_rel(p.photos)
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
    p = await session.get(ProductModel, product_id)
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
    p.photos = [rel]
    await session.commit()
    await session.refresh(p)
    return _product_to_admin(request, shop_id, p)