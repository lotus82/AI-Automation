"""Конструктор сайтов Mini App: CRUD сайтов и их страниц + публичный GET.

Особенности:
- Админские операции изолируются по организации через ``resolve_organization_scope``.
- Публичный эндпоинт ``GET /api/public/sites/{site_id}`` возвращает опубликованные страницы,
  отсортированные по ``order_index``; используется в клиентском Mini App и потому открыт.
"""

from __future__ import annotations

import logging
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.responses import FileResponse, Response

from src.api.dependencies import AsyncSessionDep, SettingsDep
from src.api.dependencies_portal import PortalUserDep
from src.api.org_scope import resolve_organization_scope
from src.domain.miniapp_embed_modules import ALLOWED_EMBED_MODULE_KEYS
from src.domain.portal_roles import ROLE_SUPER_ADMIN
from src.domain.site_menu import nav_items_for_miniapp
from src.core.config import Settings
from src.domain.site_logo_url import normalize_site_logo_url, site_uploaded_logo_public_path
from src.infrastructure.models import (
    DocumentModel,
    OrganizationModel,
    PortalUserModel,
    SiteModel,
    SitePageModel,
)

logger = logging.getLogger(__name__)

_MAX_UPLOAD = 5 * 1024 * 1024
_ALLOWED_LOGO_EXT = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})


def _site_upload_root(settings: Settings, site_id: UUID) -> Path:
    return Path(settings.site_upload_dir).resolve() / str(site_id)


def _safe_join_under(root: Path, *parts: str) -> Path | None:
    target = (root / Path(*parts)).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    return target


def _logo_ext_from_filename(name: str) -> str:
    suf = Path(name or "").suffix.lower()
    return suf if suf in _ALLOWED_LOGO_EXT else ".png"


def _clear_site_logo_files(root: Path) -> None:
    if not root.is_dir():
        return
    for p in root.glob("logo.*"):
        try:
            p.unlink()
        except OSError:
            logger.warning("sites: не удалось удалить старый логотип %s", p, exc_info=True)


async def _read_logo_upload_limit(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > _MAX_UPLOAD:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Файл больше 5 МБ")
    return data


# Админский роутер (префикс /api/sites) — под Portal JWT middleware.
router = APIRouter(prefix="/sites", tags=["sites"])

# Публичный роутер (префикс /api/public/sites) — путь помечен public в middleware.
public_router = APIRouter(prefix="/public/sites", tags=["sites-public"])


_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,126}[a-z0-9]$|^[a-z0-9]$")

# Типы страниц Mini App для МИС: без сотрудника записи и без встраиваемого модуля.
_PAGE_KINDS_MIS_SPECIAL = frozenset(
    {
        "mis_patients",
        "mis_doctor_card",
        "mis_patient_card",
        "mis_patient_profile",
        "mis_patient_diary",
        "mis_patient_tips",
        "mis_agreement",
    },
)
_ALLOWED_PAGE_KINDS = frozenset({"content", "booking", "document_reader", "profile", *_PAGE_KINDS_MIS_SPECIAL})


def _mis_audience_from_page_kind(pk: str) -> str | None:
    s = (pk or "").strip().lower()
    if s in ("mis_patients", "mis_doctor_card"):
        return "doctor"
    if s in (
        "mis_patient_card",
        "mis_patient_profile",
        "mis_patient_diary",
        "mis_patient_tips",
    ):
        return "patient"
    return None


# --- Схемы ---------------------------------------------------------------


class SiteContacts(BaseModel):
    """Контакты сайта (произвольный, но типизированный набор полей).

    Хранится целиком в JSONB: добавление новых полей не требует миграции.
    """

    phone: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=512)
    website: str | None = Field(default=None, max_length=512)
    telegram: str | None = Field(default=None, max_length=255)
    vk: str | None = Field(default=None, max_length=255)
    max: str | None = Field(default=None, max_length=255)
    whatsapp: str | None = Field(default=None, max_length=255)
    instagram: str | None = Field(default=None, max_length=255)
    payment_url: str | None = Field(
        default=None,
        max_length=1024,
        description="Ссылка на оплату (например https://sberbank.ru/qr/?uuid=…) для блока QR в страницах",
    )
    mis_patient_card_theme: dict[str, Any] | None = Field(
        default=None,
        description="Тема публичной карты пациента (МИС-сайт): accent_color, card_radius и т.д.",
    )
    mis_logo_icon: str | None = Field(
        default=None,
        max_length=64,
        description="Ключ иконки Lucide для логотипа в шапке Mini App (МИС), например stethoscope",
    )


class SiteMenuItemInput(BaseModel):
    """Один пункт нижнего меню Mini App (редактор в портале)."""

    id: str | None = Field(default=None, max_length=64, description="Стабильный id для UI; если пусто — генерируется")
    label: str = Field(min_length=1, max_length=128)
    page_id: UUID
    order_index: int = Field(default=0, ge=0, le=100_000)
    is_visible: bool = True


class SiteMenuItemPublic(BaseModel):
    """Пункт меню, как отдаётся в GET /sites/{id}."""

    id: str
    label: str
    page_id: UUID
    order_index: int
    is_visible: bool


class SiteListItem(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    site_kind: str = "standard"
    title: str
    subtitle: str
    theme_color: str
    logo_url: str | None = None
    created_at: datetime
    updated_at: datetime


class SiteDetail(SiteListItem):
    contacts: SiteContacts
    menu_items: list[SiteMenuItemPublic]
    mis_menu_items_doctor: list[SiteMenuItemPublic] = Field(default_factory=list)
    mis_menu_items_patient: list[SiteMenuItemPublic] = Field(default_factory=list)


class SiteCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    site_kind: str = Field(default="standard", max_length=32)

    @field_validator("site_kind")
    @classmethod
    def _site_kind_create(cls, v: str) -> str:
        s = (v or "standard").strip().lower()
        if s not in ("standard", "mis"):
            raise ValueError("site_kind: допустимо standard или mis")
        return s


class SiteUpdateRequest(BaseModel):
    """Частичное обновление настроек сайта. Пустые строки считаются сбросом полей."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    site_kind: str | None = Field(default=None, max_length=32)
    title: str | None = Field(default=None, max_length=255)
    subtitle: str | None = Field(default=None, max_length=512)
    logo_url: str | None = Field(default=None, max_length=1024)
    theme_color: str | None = Field(default=None, max_length=16)
    contacts: SiteContacts | None = None
    menu_items: list[SiteMenuItemInput] | None = Field(
        default=None,
        description="Полная замена меню Mini App; null — не менять",
    )
    mis_menu_items_doctor: list[SiteMenuItemInput] | None = Field(
        default=None,
        description="Меню Mini App для роли врача (site_kind=mis); null — не менять",
    )
    mis_menu_items_patient: list[SiteMenuItemInput] | None = Field(
        default=None,
        description="Меню Mini App для роли пациента (site_kind=mis); null — не менять",
    )

    @field_validator("theme_color")
    @classmethod
    def _color(cls, v: str | None) -> str | None:
        if v is None:
            return v
        s = v.strip()
        if not s:
            return "#000000"
        if not re.fullmatch(r"#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?", s):
            raise ValueError("theme_color должен быть HEX вида #RGB или #RRGGBB")
        return s

    @field_validator("site_kind")
    @classmethod
    def _site_kind_upd(cls, v: str | None) -> str | None:
        if v is None:
            return v
        s = v.strip().lower()
        if s not in ("standard", "mis"):
            raise ValueError("site_kind: допустимо standard или mis")
        return s


class SitePageItem(BaseModel):
    id: UUID
    site_id: UUID
    title: str
    slug: str
    page_kind: str = "content"
    mis_audience: str | None = None
    booking_staff_user_id: UUID | None = None
    embed_module: str | None = None
    linked_document_id: UUID | None = None
    content: str
    order_index: int
    is_published: bool
    created_at: datetime
    updated_at: datetime


class SitePageCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=128)
    content: str = Field(default="", max_length=500_000)
    order_index: int = Field(default=0, ge=0, le=10_000)
    is_published: bool = True
    page_kind: str = Field(default="content", max_length=32)
    booking_staff_user_id: UUID | None = None
    embed_module: str | None = Field(default=None, max_length=64)
    #: Для ``page_kind=document_reader`` — документ из модуля «Читатель».
    linked_document_id: UUID | None = None
    #: Для МИС-сайта и ``document_reader``: ``doctor`` | ``patient``.
    mis_audience: str | None = Field(default=None, max_length=16)

    @field_validator("embed_module")
    @classmethod
    def _embed_create(cls, v: str | None) -> str | None:
        s = (v or "").strip()
        if not s:
            return None
        if s not in ALLOWED_EMBED_MODULE_KEYS:
            raise ValueError("Неизвестный ключ встраиваемого модуля")
        return s

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        s = (v or "").strip().lower()
        if not _SLUG_RE.fullmatch(s):
            raise ValueError(
                "slug должен состоять из латиницы/цифр/дефисов, без пробелов и спецсимволов",
            )
        return s

    @field_validator("page_kind")
    @classmethod
    def _page_kind(cls, v: str) -> str:
        s = (v or "content").strip().lower()
        if s not in _ALLOWED_PAGE_KINDS:
            raise ValueError(
                "page_kind: допустимо content, booking или спец-страницы МИС (mis_patients, mis_doctor_card, …)",
            )
        return s

    @model_validator(mode="after")
    def _booking_staff_required(self) -> SitePageCreateRequest:
        if self.page_kind == "booking" and self.booking_staff_user_id is None:
            raise ValueError("Для страницы записи укажите сотрудника (booking_staff_user_id)")
        if self.page_kind == "booking" and self.embed_module:
            raise ValueError("Для страницы записи встраиваемый модуль не используется (оставьте пустым)")
        if self.page_kind in _PAGE_KINDS_MIS_SPECIAL:
            if self.embed_module:
                raise ValueError("Для спец-страницы МИС встраиваемый модуль не используется")
            if self.booking_staff_user_id is not None:
                raise ValueError("Для спец-страницы МИС не указывайте сотрудника записи")
        if self.page_kind == "document_reader":
            if not self.linked_document_id:
                raise ValueError("Для страницы «Читатель» укажите linked_document_id")
            if self.embed_module:
                raise ValueError("Для страницы «Читатель» встраиваемый модуль не используется")
            if self.booking_staff_user_id is not None:
                raise ValueError("Для страницы «Читатель» не указывайте сотрудника записи")
        if self.page_kind == "profile":
            if self.booking_staff_user_id is not None:
                raise ValueError("Для страницы «Профиль» не указывайте сотрудника записи")
            if self.embed_module:
                raise ValueError("Для страницы «Профиль» встраиваемый модуль не используется")
            if self.linked_document_id is not None:
                raise ValueError("Для страницы «Профиль» не укажите документ (linked_document_id)")
        return self


class SitePageUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=128)
    content: str | None = Field(default=None, max_length=500_000)
    order_index: int | None = Field(default=None, ge=0, le=10_000)
    is_published: bool | None = None
    page_kind: str | None = Field(default=None, max_length=32)
    booking_staff_user_id: UUID | None = None
    embed_module: str | None = Field(default=None, max_length=64)
    linked_document_id: UUID | None = None
    mis_audience: str | None = Field(default=None, max_length=16)

    @field_validator("embed_module")
    @classmethod
    def _embed_upd(cls, v: str | None) -> str | None:
        if v is None:
            return v
        s = v.strip()
        if not s:
            return None
        if s not in ALLOWED_EMBED_MODULE_KEYS:
            raise ValueError("Неизвестный ключ встраиваемого модуля")
        return s

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str | None) -> str | None:
        if v is None:
            return v
        s = (v or "").strip().lower()
        if not _SLUG_RE.fullmatch(s):
            raise ValueError(
                "slug должен состоять из латиницы/цифр/дефисов, без пробелов и спецсимволов",
            )
        return s

    @field_validator("page_kind")
    @classmethod
    def _page_kind_upd(cls, v: str | None) -> str | None:
        if v is None:
            return v
        s = v.strip().lower()
        if s not in _ALLOWED_PAGE_KINDS:
            raise ValueError(
                "page_kind: допустимо content, booking или спец-страницы МИС (mis_patients, mis_doctor_card, …)",
            )
        return s


class PublicSitePage(BaseModel):
    """Страница для публичного Mini App (без служебных полей и без черновиков)."""

    id: UUID
    title: str
    slug: str
    page_kind: str = "content"
    mis_audience: str | None = None
    booking_staff_user_id: UUID | None = None
    embed_module: str | None = None
    linked_document_id: UUID | None = None
    content: str
    order_index: int


class PublicNavItem(BaseModel):
    """Пункт нижнего меню (подпись в Tabbar + slug страницы)."""

    label: str
    slug: str


class PublicSiteResponse(BaseModel):
    id: UUID
    name: str
    site_kind: str = "standard"
    title: str
    subtitle: str
    logo_url: str | None = None
    theme_color: str
    contacts: SiteContacts
    pages: list[PublicSitePage]
    nav_items: list[PublicNavItem]
    mis_nav_items_doctor: list[PublicNavItem] = Field(default_factory=list)
    mis_nav_items_patient: list[PublicNavItem] = Field(default_factory=list)


# --- Helpers -------------------------------------------------------------


def _menu_public_from_db(raw: object) -> list[SiteMenuItemPublic]:
    """Нормализует JSONB ``menu_items`` для ответа API."""
    if not raw or not isinstance(raw, list):
        return []
    out: list[SiteMenuItemPublic] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        pid_raw = item.get("page_id")
        if not pid_raw:
            continue
        try:
            page_id = UUID(str(pid_raw))
        except ValueError:
            continue
        iid = str(item.get("id") or "").strip() or str(uuid.uuid4())
        out.append(
            SiteMenuItemPublic(
                id=iid,
                label=str(item.get("label") or ""),
                page_id=page_id,
                order_index=int(item.get("order_index", 0) or 0),
                is_visible=bool(item.get("is_visible", True)),
            ),
        )
    out.sort(key=lambda x: (x.order_index, x.label))
    return out


def _site_kind_str(row: SiteModel) -> str:
    raw = getattr(row, "site_kind", None) or "standard"
    s = str(raw).strip().lower()
    return s if s in ("standard", "mis") else "standard"


def _site_to_detail(row: SiteModel) -> SiteDetail:
    return SiteDetail(
        id=row.id,
        organization_id=row.organization_id,
        name=row.name,
        site_kind=_site_kind_str(row),
        title=row.title or "",
        subtitle=row.subtitle or "",
        theme_color=row.theme_color or "#000000",
        logo_url=normalize_site_logo_url((row.logo_url or "").strip() or None),
        contacts=SiteContacts.model_validate(row.contacts or {}),
        menu_items=_menu_public_from_db(getattr(row, "menu_items", None)),
        mis_menu_items_doctor=_menu_public_from_db(getattr(row, "mis_menu_items_doctor", None)),
        mis_menu_items_patient=_menu_public_from_db(getattr(row, "mis_menu_items_patient", None)),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _site_to_list_item(row: SiteModel) -> SiteListItem:
    return SiteListItem(
        id=row.id,
        organization_id=row.organization_id,
        name=row.name,
        site_kind=_site_kind_str(row),
        title=row.title or "",
        subtitle=row.subtitle or "",
        theme_color=row.theme_color or "#000000",
        logo_url=normalize_site_logo_url((row.logo_url or "").strip() or None),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _page_to_item(row: SitePageModel) -> SitePageItem:
    em = (getattr(row, "embed_module", None) or "").strip() or None
    ma_raw = getattr(row, "mis_audience", None)
    ma = (str(ma_raw).strip().lower() if ma_raw else None) or None
    if ma not in (None, "doctor", "patient"):
        ma = None
    return SitePageItem(
        id=row.id,
        site_id=row.site_id,
        title=row.title,
        slug=row.slug,
        page_kind=(row.page_kind or "content").strip() or "content",
        mis_audience=ma,
        booking_staff_user_id=row.booking_staff_user_id,
        embed_module=em,
        linked_document_id=getattr(row, "linked_document_id", None),
        content=row.content or "",
        order_index=int(row.order_index or 0),
        is_published=bool(row.is_published),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _validate_linked_document_for_site(
    session: AsyncSessionDep,
    site_org_id: UUID,
    doc_id: UUID | None,
) -> None:
    if doc_id is None:
        return
    d = await session.get(DocumentModel, doc_id)
    if d is None or d.organization_id != site_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Документ не найден или не принадлежит организации этого сайта",
        )


async def _validate_booking_staff_for_site(
    session: AsyncSessionDep,
    site_org_id: UUID,
    staff_id: UUID | None,
) -> None:
    if staff_id is None:
        return
    u = await session.get(PortalUserModel, staff_id)
    if u is None or u.organization_id != site_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Указанный сотрудник не принадлежит организации этого сайта",
        )


def _menu_item_sort_key(x: SiteMenuItemInput) -> tuple[int, str]:
    """Безопасный ключ сортировки: ``None`` в order_index не должен ломать ``sorted`` (TypeError)."""
    try:
        oi = int(x.order_index) if x.order_index is not None else 0
    except (TypeError, ValueError):
        oi = 0
    return (oi, str(x.page_id))


def _effective_mis_audience_for_page(mis_audience_raw: object, page_kind: str) -> str | None:
    """Эффективная аудитория страницы: колонка ``mis_audience`` или вывод из ``page_kind`` (legacy без backfill)."""
    s = str(mis_audience_raw or "").strip().lower()
    if s in ("doctor", "patient"):
        return s
    return _mis_audience_from_page_kind(page_kind)


async def _validate_mis_menu_for_site(
    session: AsyncSessionDep,
    site_id: UUID,
    items_in: list[SiteMenuItemInput],
    audience: str,
) -> list[dict]:
    """Сохраняет JSON меню МИС; все ``page_id`` должны указывать на страницы с тем же ``mis_audience``."""
    aud = audience.strip().lower()
    if aud not in ("doctor", "patient"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Недопустимая роль меню МИС")
    pids = [it.page_id for it in items_in]
    if len(pids) != len(set(pids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="В меню нельзя дважды привязать одну и ту же страницу",
        )
    if not pids:
        return []
    # Колонка ``mis_audience`` есть после миграции 050; в старых образах/БД её может не быть в метаданных — не падаем.
    tbl = SitePageModel.__table__
    c = tbl.c
    has_mis_audience_col = "mis_audience" in tbl.columns.keys()
    stmt = (
        select(c.id, c.mis_audience, c.page_kind).where(
            c.site_id == site_id,
            c.id.in_(pids),
        )
        if has_mis_audience_col
        else select(c.id, c.page_kind).where(
            c.site_id == site_id,
            c.id.in_(pids),
        )
    )
    rows = (await session.execute(stmt)).all()
    if len(rows) != len(pids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="В меню указана страница, не принадлежащая этому сайту",
        )
    for row in rows:
        if has_mis_audience_col:
            _rid, rau, pk = row
        else:
            _rid, pk = row
            rau = None
        pk_norm = (pk or "content").strip().lower()
        effective = _effective_mis_audience_for_page(rau, pk_norm)
        if effective != aud:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="В меню МИС можно указывать только страницы той же роли (врач или пациент)",
            )
    stored: list[dict] = []
    for it in sorted(items_in, key=_menu_item_sort_key):
        iid = (it.id or "").strip() or str(uuid.uuid4())
        stored.append(
            {
                "id": iid,
                "label": (it.label or "").strip() or "Пункт",
                "page_id": str(it.page_id),
                "order_index": int(it.order_index),
                "is_visible": bool(it.is_visible),
            },
        )
    return stored


def _resolve_site_org_scope(user, organization_id: UUID | None) -> UUID:
    """Организация, в чьём контексте работаем. Для super_admin без override — 400."""
    scope = resolve_organization_scope(user, organization_id)
    if scope is None:
        if user.role == ROLE_SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Для супер-админа нужно указать organization_id",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет организации",
        )
    return scope


async def _get_site_for_user(
    session: AsyncSessionDep,
    site_id: UUID,
    org_scope: UUID,
) -> SiteModel:
    """Достаёт сайт с проверкой принадлежности организации. 404 если не найден в scope."""
    row = await session.get(SiteModel, site_id)
    if row is None or row.organization_id != org_scope:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сайт не найден")
    return row


# --- Эндпоинты: сайты ----------------------------------------------------


@router.get("", response_model=list[SiteListItem])
async def list_sites(
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(
        default=None,
        description="Супер-админ: id организации (обязателен). Остальные — игнорируется, берётся из JWT.",
    ),
    site_kind: str | None = Query(
        default=None,
        description="Фильтр: standard (обычные сайты) или mis (конструктор МИС).",
    ),
) -> list[SiteListItem]:
    """Список сайтов организации."""
    scope = _resolve_site_org_scope(user, organization_id)
    stmt = select(SiteModel).where(SiteModel.organization_id == scope)
    if site_kind is not None and str(site_kind).strip():
        sk = str(site_kind).strip().lower()
        if sk not in ("standard", "mis"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Параметр site_kind: допустимо standard или mis",
            )
        stmt = stmt.where(SiteModel.site_kind == sk)
    rows = (await session.execute(stmt.order_by(SiteModel.updated_at.desc()))).scalars().all()
    return [_site_to_list_item(r) for r in rows]


@router.post("", response_model=SiteDetail, status_code=status.HTTP_201_CREATED)
async def create_site(
    body: SiteCreateRequest,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(default=None),
) -> SiteDetail:
    """Создание сайта. Настройки заполняются позже через PUT."""
    scope = _resolve_site_org_scope(user, organization_id)
    org = await session.get(OrganizationModel, scope)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Организация не найдена")
    row = SiteModel(
        organization_id=scope,
        name=body.name.strip(),
        site_kind=body.site_kind,
        title="",
        subtitle="",
        logo_url=None,
        theme_color="#000000",
        contacts={},
        menu_items=[],
        mis_menu_items_doctor=[],
        mis_menu_items_patient=[],
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _site_to_detail(row)


@router.get("/{site_id}", response_model=SiteDetail)
async def get_site(
    site_id: UUID,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(default=None),
) -> SiteDetail:
    scope = _resolve_site_org_scope(user, organization_id)
    row = await _get_site_for_user(session, site_id, scope)
    return _site_to_detail(row)


@router.put("/{site_id}", response_model=SiteDetail)
async def update_site(
    site_id: UUID,
    body: SiteUpdateRequest,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(default=None),
) -> SiteDetail:
    """Частичное обновление настроек сайта (название, заголовок, цвет, контакты и т.д.)."""
    scope = _resolve_site_org_scope(user, organization_id)
    row = await _get_site_for_user(session, site_id, scope)

    if body.name is not None:
        row.name = body.name.strip()
    if body.site_kind is not None:
        row.site_kind = body.site_kind
    if body.title is not None:
        row.title = body.title.strip()
    if body.subtitle is not None:
        row.subtitle = body.subtitle.strip()
    if body.logo_url is not None:
        row.logo_url = body.logo_url.strip() or None
    if body.theme_color is not None:
        row.theme_color = body.theme_color
    if body.contacts is not None:
        # model_dump(exclude_none=True) — не храним None-поля, чтобы JSONB не разрастался
        row.contacts = body.contacts.model_dump(exclude_none=True)

    if body.menu_items is not None:
        pids = [it.page_id for it in body.menu_items]
        if len(pids) != len(set(pids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="В меню нельзя дважды привязать одну и ту же страницу",
            )
        if pids:
            found = (
                await session.execute(
                    select(SitePageModel.id).where(
                        SitePageModel.site_id == site_id,
                        SitePageModel.id.in_(pids),
                    )
                )
            ).scalars().all()
            if set(found) != set(pids):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="В меню указана страница, не принадлежащая этому сайту",
                )
        stored: list[dict] = []
        for it in sorted(body.menu_items, key=_menu_item_sort_key):
            iid = (it.id or "").strip() or str(uuid.uuid4())
            stored.append(
                {
                    "id": iid,
                    "label": it.label.strip(),
                    "page_id": str(it.page_id),
                    "order_index": int(it.order_index),
                    "is_visible": bool(it.is_visible),
                },
            )
        row.menu_items = stored

    if body.mis_menu_items_doctor is not None:
        row.mis_menu_items_doctor = await _validate_mis_menu_for_site(
            session,
            site_id,
            body.mis_menu_items_doctor,
            "doctor",
        )
    if body.mis_menu_items_patient is not None:
        row.mis_menu_items_patient = await _validate_mis_menu_for_site(
            session,
            site_id,
            body.mis_menu_items_patient,
            "patient",
        )

    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _site_to_detail(row)


@router.post("/{site_id}/logo", response_model=SiteDetail)
async def upload_site_logo(
    site_id: UUID,
    user: PortalUserDep,
    session: AsyncSessionDep,
    settings: SettingsDep,
    organization_id: UUID | None = Query(default=None),
    file: UploadFile = File(...),
) -> SiteDetail:
    """Загрузка логотипа: файл на диске + публичный URL в ``logo_url`` (для Mini App без JWT)."""
    scope = _resolve_site_org_scope(user, organization_id)
    row = await _get_site_for_user(session, site_id, scope)
    raw = await _read_logo_upload_limit(file)
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Пустой файл")
    ext = _logo_ext_from_filename(file.filename or "")
    rel = f"logo{ext}"
    root = _site_upload_root(settings, site_id)
    _clear_site_logo_files(root)
    root.mkdir(parents=True, exist_ok=True)
    dest = root / rel
    dest.write_bytes(raw)
    row.logo_url = site_uploaded_logo_public_path(site_id, rel)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _site_to_detail(row)


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site(
    site_id: UUID,
    user: PortalUserDep,
    session: AsyncSessionDep,
    settings: SettingsDep,
    organization_id: UUID | None = Query(default=None),
) -> Response:
    scope = _resolve_site_org_scope(user, organization_id)
    row = await _get_site_for_user(session, site_id, scope)
    await session.delete(row)
    await session.commit()
    upload_root = _site_upload_root(settings, site_id)
    if upload_root.exists():
        shutil.rmtree(upload_root, ignore_errors=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Эндпоинты: страницы сайта ------------------------------------------


@router.get("/{site_id}/pages", response_model=list[SitePageItem])
async def list_site_pages(
    site_id: UUID,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(default=None),
) -> list[SitePageItem]:
    """Все страницы сайта (в т.ч. черновики), отсортированные по order_index, затем created_at."""
    scope = _resolve_site_org_scope(user, organization_id)
    await _get_site_for_user(session, site_id, scope)
    rows = (
        await session.execute(
            select(SitePageModel)
            .where(SitePageModel.site_id == site_id)
            .order_by(SitePageModel.order_index.asc(), SitePageModel.created_at.asc())
        )
    ).scalars().all()
    return [_page_to_item(r) for r in rows]


@router.post("/{site_id}/pages", response_model=SitePageItem, status_code=status.HTTP_201_CREATED)
async def create_site_page(
    site_id: UUID,
    body: SitePageCreateRequest,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(default=None),
) -> SitePageItem:
    scope = _resolve_site_org_scope(user, organization_id)
    site_row = await _get_site_for_user(session, site_id, scope)
    sk0 = _site_kind_str(site_row)
    pk = (body.page_kind or "content").strip().lower()
    if sk0 == "mis" and pk == "profile":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Тип страницы «профиль» доступен только для обычного (не МИС) сайта",
        )
    sid = body.booking_staff_user_id if pk == "booking" else None
    if sid is not None:
        await _validate_booking_staff_for_site(session, scope, sid)
    embed = body.embed_module if pk == "content" else None
    sk = _site_kind_str(site_row)
    mis_aud: str | None = None
    if sk == "mis":
        if pk == "document_reader":
            ma = (body.mis_audience or "").strip().lower()
            if ma not in ("doctor", "patient"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Для страницы «Читатель» на МИС-сайте укажите mis_audience: doctor или patient",
                )
            mis_aud = ma
        elif pk == "mis_agreement":
            mis_aud = None
        else:
            mis_aud = _mis_audience_from_page_kind(pk)
            if mis_aud is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Для МИС-сайта создавайте только страницы разделов врача или пациента",
                )
    linked_id = body.linked_document_id if pk == "document_reader" else None
    if pk == "document_reader":
        await _validate_linked_document_for_site(session, scope, linked_id)
    row = SitePageModel(
        site_id=site_id,
        title=body.title.strip(),
        slug=body.slug,
        page_kind=pk,
        mis_audience=mis_aud,
        booking_staff_user_id=sid,
        embed_module=embed,
        linked_document_id=linked_id,
        content=body.content or "",
        order_index=body.order_index,
        is_published=body.is_published,
    )
    session.add(row)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Страница с таким slug уже существует на этом сайте",
        ) from e
    await session.refresh(row)
    return _page_to_item(row)


@router.put("/{site_id}/pages/{page_id}", response_model=SitePageItem)
async def update_site_page(
    site_id: UUID,
    page_id: UUID,
    body: SitePageUpdateRequest,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(default=None),
) -> SitePageItem:
    scope = _resolve_site_org_scope(user, organization_id)
    site_row = await _get_site_for_user(session, site_id, scope)
    row = await session.get(SitePageModel, page_id)
    if row is None or row.site_id != site_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Страница не найдена")
    if _site_kind_str(site_row) == "mis" and (body.page_kind or "").strip().lower() == "profile":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Тип страницы «профиль» доступен только для обычного (не МИС) сайта",
        )

    if body.title is not None:
        row.title = body.title.strip()
    if body.slug is not None:
        row.slug = body.slug
    if body.content is not None:
        row.content = body.content
    if body.order_index is not None:
        row.order_index = int(body.order_index)
    if body.is_published is not None:
        row.is_published = bool(body.is_published)
    fs = body.model_fields_set
    if body.page_kind is not None:
        row.page_kind = body.page_kind.strip().lower()
        if row.page_kind != "booking":
            row.booking_staff_user_id = None
    if "booking_staff_user_id" in fs:
        row.booking_staff_user_id = body.booking_staff_user_id
    if "embed_module" in fs:
        row.embed_module = body.embed_module
    if "linked_document_id" in fs:
        row.linked_document_id = body.linked_document_id

    if (row.page_kind or "content") == "booking" and row.booking_staff_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Для страницы записи укажите сотрудника (booking_staff_user_id)",
        )
    if row.booking_staff_user_id is not None:
        await _validate_booking_staff_for_site(session, scope, row.booking_staff_user_id)
    pkf = (row.page_kind or "content").strip().lower()
    if pkf == "booking":
        row.embed_module = None
        row.linked_document_id = None
    elif pkf == "content":
        row.booking_staff_user_id = None
        row.linked_document_id = None
    elif pkf == "document_reader":
        row.booking_staff_user_id = None
        row.embed_module = None
    else:
        row.embed_module = None
        row.booking_staff_user_id = None
        row.linked_document_id = None

    if pkf == "document_reader":
        if row.linked_document_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Укажите linked_document_id для страницы «Читатель»",
            )
        await _validate_linked_document_for_site(session, scope, row.linked_document_id)

    sk = _site_kind_str(site_row)
    if sk == "mis":
        if pkf == "document_reader":
            ma_src = body.mis_audience if "mis_audience" in fs else row.mis_audience
            ma = (str(ma_src or "").strip().lower() or None)
            if ma not in ("doctor", "patient"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Для страницы «Читатель» на МИС-сайте укажите mis_audience: doctor или patient",
                )
            row.mis_audience = ma
        elif pkf == "mis_agreement":
            row.mis_audience = None
        else:
            mis_aud = _mis_audience_from_page_kind(pkf)
            if mis_aud is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Для МИС-сайта укажите тип страницы раздела врача или пациента",
                )
            row.mis_audience = mis_aud
    else:
        row.mis_audience = None

    session.add(row)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Страница с таким slug уже существует на этом сайте",
        ) from e
    await session.refresh(row)
    return _page_to_item(row)


@router.delete("/{site_id}/pages/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site_page(
    site_id: UUID,
    page_id: UUID,
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(default=None),
) -> Response:
    scope = _resolve_site_org_scope(user, organization_id)
    await _get_site_for_user(session, site_id, scope)
    row = await session.get(SitePageModel, page_id)
    if row is None or row.site_id != site_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Страница не найдена")
    await session.delete(row)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Публичный эндпоинт (для клиентского Mini App) ----------------------


@public_router.get("/assets/{site_id}/{rest:path}")
async def get_public_site_asset(
    site_id: UUID,
    rest: str,
    settings: SettingsDep,
) -> FileResponse:
    """Раздача загруженного логотипа (и др. файлов сайта) без авторизации."""
    if ".." in rest or rest.startswith(("/", "\\")):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Не найдено")
    root = _site_upload_root(settings, site_id)
    path = _safe_join_under(root, *rest.split("/"))
    if path is None or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Не найдено")
    return FileResponse(path)


@public_router.get("/{site_id}", response_model=PublicSiteResponse)
async def get_public_site(site_id: UUID, session: AsyncSessionDep) -> PublicSiteResponse:
    """Публичная витрина сайта: возвращает только ОПУБЛИКОВАННЫЕ страницы."""
    site = await session.get(SiteModel, site_id)
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сайт не найден")

    pages_rows = (
        await session.execute(
            select(SitePageModel)
            .where(
                SitePageModel.site_id == site_id,
                SitePageModel.is_published.is_(True),
            )
            .order_by(SitePageModel.order_index.asc(), SitePageModel.created_at.asc())
        )
    ).scalars().all()

    menu_raw = site.menu_items if isinstance(site.menu_items, list) else None
    nav_dtos = nav_items_for_miniapp(menu_raw, pages_rows)

    sk = _site_kind_str(site)
    mis_nav_doctor: list = []
    mis_nav_patient: list = []
    if sk == "mis":
        doc_raw = (
            site.mis_menu_items_doctor if isinstance(getattr(site, "mis_menu_items_doctor", None), list) else None
        )
        pat_raw = (
            site.mis_menu_items_patient if isinstance(getattr(site, "mis_menu_items_patient", None), list) else None
        )

        def _aud_pages(aud: str) -> list:
            a = aud.strip().lower()
            return [p for p in pages_rows if (getattr(p, "mis_audience", None) or "").strip().lower() == a]

        mis_nav_doctor = nav_items_for_miniapp(doc_raw, _aud_pages("doctor"))
        mis_nav_patient = nav_items_for_miniapp(pat_raw, _aud_pages("patient"))

    def _pub_ma(p: SitePageModel) -> str | None:
        raw = getattr(p, "mis_audience", None)
        ma = (str(raw).strip().lower() if raw else None) or None
        return ma if ma in ("doctor", "patient") else None

    return PublicSiteResponse(
        id=site.id,
        name=site.name,
        site_kind=sk,
        title=site.title or "",
        subtitle=site.subtitle or "",
        logo_url=normalize_site_logo_url((site.logo_url or "").strip() or None),
        theme_color=site.theme_color or "#000000",
        contacts=SiteContacts.model_validate(site.contacts or {}),
        pages=[
            PublicSitePage(
                id=p.id,
                title=p.title,
                slug=p.slug,
                page_kind=(p.page_kind or "content").strip() or "content",
                mis_audience=_pub_ma(p),
                booking_staff_user_id=p.booking_staff_user_id,
                embed_module=(getattr(p, "embed_module", None) or "").strip() or None,
                linked_document_id=getattr(p, "linked_document_id", None),
                content=p.content or "",
                order_index=int(p.order_index or 0),
            )
            for p in pages_rows
        ],
        nav_items=[PublicNavItem(label=n.label, slug=n.slug) for n in nav_dtos],
        mis_nav_items_doctor=[PublicNavItem(label=n.label, slug=n.slug) for n in mis_nav_doctor],
        mis_nav_items_patient=[PublicNavItem(label=n.label, slug=n.slug) for n in mis_nav_patient],
    )
