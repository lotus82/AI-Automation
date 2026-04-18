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
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.responses import FileResponse, Response

from src.api.dependencies import AsyncSessionDep, SettingsDep
from src.api.dependencies_portal import PortalUserDep
from src.api.org_scope import resolve_organization_scope
from src.domain.portal_roles import ROLE_SUPER_ADMIN
from src.domain.site_menu import nav_items_for_miniapp
from src.core.config import Settings
from src.domain.site_logo_url import normalize_site_logo_url, site_uploaded_logo_public_path
from src.infrastructure.models import OrganizationModel, SiteModel, SitePageModel

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
    title: str
    subtitle: str
    theme_color: str
    logo_url: str | None = None
    created_at: datetime
    updated_at: datetime


class SiteDetail(SiteListItem):
    contacts: SiteContacts
    menu_items: list[SiteMenuItemPublic]


class SiteCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class SiteUpdateRequest(BaseModel):
    """Частичное обновление настроек сайта. Пустые строки считаются сбросом полей."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    title: str | None = Field(default=None, max_length=255)
    subtitle: str | None = Field(default=None, max_length=512)
    logo_url: str | None = Field(default=None, max_length=1024)
    theme_color: str | None = Field(default=None, max_length=16)
    contacts: SiteContacts | None = None
    menu_items: list[SiteMenuItemInput] | None = Field(
        default=None,
        description="Полная замена меню Mini App; null — не менять",
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


class SitePageItem(BaseModel):
    id: UUID
    site_id: UUID
    title: str
    slug: str
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

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        s = (v or "").strip().lower()
        if not _SLUG_RE.fullmatch(s):
            raise ValueError(
                "slug должен состоять из латиницы/цифр/дефисов, без пробелов и спецсимволов",
            )
        return s


class SitePageUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=128)
    content: str | None = Field(default=None, max_length=500_000)
    order_index: int | None = Field(default=None, ge=0, le=10_000)
    is_published: bool | None = None

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


class PublicSitePage(BaseModel):
    """Страница для публичного Mini App (без служебных полей и без черновиков)."""

    id: UUID
    title: str
    slug: str
    content: str
    order_index: int


class PublicNavItem(BaseModel):
    """Пункт нижнего меню (подпись в Tabbar + slug страницы)."""

    label: str
    slug: str


class PublicSiteResponse(BaseModel):
    id: UUID
    name: str
    title: str
    subtitle: str
    logo_url: str | None = None
    theme_color: str
    contacts: SiteContacts
    pages: list[PublicSitePage]
    nav_items: list[PublicNavItem]


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


def _site_to_detail(row: SiteModel) -> SiteDetail:
    return SiteDetail(
        id=row.id,
        organization_id=row.organization_id,
        name=row.name,
        title=row.title or "",
        subtitle=row.subtitle or "",
        theme_color=row.theme_color or "#000000",
        logo_url=normalize_site_logo_url((row.logo_url or "").strip() or None),
        contacts=SiteContacts.model_validate(row.contacts or {}),
        menu_items=_menu_public_from_db(getattr(row, "menu_items", None)),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _site_to_list_item(row: SiteModel) -> SiteListItem:
    return SiteListItem(
        id=row.id,
        organization_id=row.organization_id,
        name=row.name,
        title=row.title or "",
        subtitle=row.subtitle or "",
        theme_color=row.theme_color or "#000000",
        logo_url=normalize_site_logo_url((row.logo_url or "").strip() or None),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _page_to_item(row: SitePageModel) -> SitePageItem:
    return SitePageItem(
        id=row.id,
        site_id=row.site_id,
        title=row.title,
        slug=row.slug,
        content=row.content or "",
        order_index=int(row.order_index or 0),
        is_published=bool(row.is_published),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


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
) -> list[SiteListItem]:
    """Список сайтов организации."""
    scope = _resolve_site_org_scope(user, organization_id)
    rows = (
        await session.execute(
            select(SiteModel)
            .where(SiteModel.organization_id == scope)
            .order_by(SiteModel.updated_at.desc())
        )
    ).scalars().all()
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
        title="",
        subtitle="",
        logo_url=None,
        theme_color="#000000",
        contacts={},
        menu_items=[],
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
        for it in sorted(body.menu_items, key=lambda x: (x.order_index, str(x.page_id))):
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
    await _get_site_for_user(session, site_id, scope)
    row = SitePageModel(
        site_id=site_id,
        title=body.title.strip(),
        slug=body.slug,
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
    await _get_site_for_user(session, site_id, scope)
    row = await session.get(SitePageModel, page_id)
    if row is None or row.site_id != site_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Страница не найдена")

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

    return PublicSiteResponse(
        id=site.id,
        name=site.name,
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
                content=p.content or "",
                order_index=int(p.order_index or 0),
            )
            for p in pages_rows
        ],
        nav_items=[PublicNavItem(label=n.label, slug=n.slug) for n in nav_dtos],
    )
