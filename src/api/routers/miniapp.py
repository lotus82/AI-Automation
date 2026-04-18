"""Mini App MAX: публичная авторизация по ИНН организации и JWT (aud=miniapp).

Сценарий:
1. Пользователь открывает Web App бота организации по ссылке ``https://<host>/inn/<inn>``.
2. Фронтенд собирает параметры запуска мессенджера (строка ``init_data``) и отправляет
   на ``POST /api/miniapp/auth`` вместе с ``inn``.
3. Бэкенд находит организацию, проверяет ``init_data`` (TODO: криптоподпись через токен
   бота этой организации), делает upsert в ``mini_app_users`` по (organization_id, chat_id)
   и возвращает JWT с ``typ/aud=miniapp``.
4. Фронт передаёт JWT в заголовке ``Authorization: Bearer …`` для последующих вызовов
   ``/api/miniapp/me`` и т.п.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Annotated
from urllib.parse import parse_qsl
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.api.dependencies import AsyncSessionDep, RedisDep
from src.api.dependencies_portal import PortalUserDep
from src.core.config import get_settings
from src.domain import system_setting_keys as sk
from src.domain.portal_roles import ROLE_DIRECTOR, ROLE_ORG_ADMIN, ROLE_SUPER_ADMIN
from src.domain.site_logo_url import normalize_site_logo_url
from src.domain.site_menu import nav_items_for_miniapp
from src.infrastructure.models import MiniAppUserModel, OrganizationModel, SiteModel, SitePageModel
from src.infrastructure.portal_security import (
    create_miniapp_access_token,
    decode_miniapp_token,
)
from src.infrastructure.repositories import PostgresSettingsRepository

logger = logging.getLogger(__name__)

# Публичный роутер Mini App (монтируется как /api/miniapp) — пропускается middleware.
router = APIRouter(prefix="/miniapp", tags=["miniapp"])

# Публичный роутер конфигурации Mini App (монтируется как /api/public/miniapp) —
# отдаёт witching content по ИНН без авторизации, помечен public в middleware.
public_router = APIRouter(prefix="/public/miniapp", tags=["miniapp-public"])

# Административный роутер (монтируется как /api/portal/miniapp) — под Portal JWT.
admin_router = APIRouter(prefix="/portal/miniapp", tags=["miniapp-admin"])


# --- Схемы ---------------------------------------------------------------


class MiniAppAuthRequest(BaseModel):
    """Тело запроса авторизации Mini App."""

    inn: str = Field(min_length=1, max_length=32, description="ИНН организации из ссылки /inn/<inn>")
    init_data: str = Field(
        min_length=1,
        max_length=4096,
        description=(
            "Сырая строка инициализации от мессенджера (query-string). "
            "Обязательно содержит chat_id; ожидается подпись (hash) — валидация ниже."
        ),
    )
    # Опциональный override для совместимости с мессенджерами, которые не кладут имя в init_data
    name_hint: str | None = Field(default=None, max_length=255)


class MiniAppAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user_id: UUID
    organization_id: UUID
    chat_id: str
    name: str | None = None


class MiniAppUserPublic(BaseModel):
    """Карточка пользователя Mini App для админ-панели."""

    id: UUID
    chat_id: str
    name: str | None
    created_at: datetime
    updated_at: datetime


class MiniAppMe(BaseModel):
    """Профиль текущего пользователя Mini App (внутри мессенджера)."""

    user_id: UUID
    organization_id: UUID
    chat_id: str
    name: str | None
    organization_name: str
    organization_display_name: str | None = None


# --- init_data parsing / validation -------------------------------------

# Константа для HMAC secret_key (стандарт Telegram Web Apps).
# Если документация MAX предписывает другую константу — поменять здесь в одном месте.
_INIT_DATA_HMAC_KEY = b"WebAppData"


async def _verify_init_data_signature(init_data: str, bot_token: str) -> dict[str, str]:
    """HMAC-SHA256 верификация ``init_data`` Web App мессенджера.

    Алгоритм (совместим с Telegram Web Apps, ожидаемый контракт MAX):
      1. Разбираем query-string ``init_data`` в dict ``parsed_data``.
      2. Извлекаем и удаляем поле ``hash`` (иначе 401).
      3. Строим ``data_check_string`` — отсортированные по ключу пары ``key=value``,
         соединённые символом ``\\n``.
      4. ``secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)``.
      5. ``calculated_hash = HMAC_SHA256(key=secret_key, msg=data_check_string).hexdigest()``.
      6. Сравниваем с ``received_hash`` через ``hmac.compare_digest`` (защита от timing-атак).

    Возвращает dict ПРОВЕРЕННЫХ полей (без ``hash``).
    """
    if not bot_token or not str(bot_token).strip():
        # Токен организации не задан — без него верификация невозможна.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "У организации не настроен MAX_BOT_TOKEN: невозможно проверить подпись init_data. "
                "Администратор должен сохранить токен бота в настройках организации."
            ),
        )

    raw = (init_data or "").strip()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Не переданы стартовые параметры мессенджера (WebAppData). "
                "Откройте Mini App из бота MAX."
            ),
        )

    # parse_qsl: разбивает по '&', URL-декодирует значения — соответствует шагам 1-4
    # валидации MAX (https://dev.max.ru/docs/webapps/validation).
    parsed_data = dict(parse_qsl(raw, keep_blank_values=True))

    if "hash" not in parsed_data:
        # Попадаем сюда, если с фронта пришла строка без hash (например, содержимое
        # ``#WebAppData=…`` не было извлечено и прилетел dev-fallback `chat_id=…`).
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "В данных авторизации отсутствует подпись (hash). "
                "Откройте Mini App из бота MAX — клиент должен передать параметр "
                "WebAppData из URL-фрагмента."
            ),
        )

    received_hash = parsed_data.pop("hash")

    sorted_keys = sorted(parsed_data.keys())
    data_check_string = "\n".join(f"{k}={parsed_data[k]}" for k in sorted_keys)

    secret_key = hmac.new(
        key=_INIT_DATA_HMAC_KEY,
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    calculated_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недействительная подпись данных (Invalid Signature)",
        )

    return parsed_data


def _json_object_from_parsed(parsed: dict[str, str], key: str) -> dict:
    """Достаёт вложенный JSON-объект по ключу из проверенных данных.

    У MAX поля ``user`` и ``chat`` — сериализованные JSON-объекты (см.
    https://dev.max.ru/docs/webapps/bridge). Если ключа нет или значение не JSON-
    объект, возвращаем пустой dict.
    """
    raw = parsed.get(key)
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return obj if isinstance(obj, dict) else {}


def _user_object_from_parsed(parsed: dict[str, str]) -> dict:
    """Алиас для user-объекта (обратная совместимость с вызывающим кодом)."""
    return _json_object_from_parsed(parsed, "user")


def _extract_chat_id(parsed: dict[str, str]) -> str:
    """Достаёт chat_id из ПРОВЕРЕННЫХ полей init_data MAX.

    Согласно https://dev.max.ru/docs/webapps/bridge, MAX передаёт объект ``chat`` в
    формате ``{"id": 12345, "type": "DIALOG"}``. Идентификатор пользователя —
    в объекте ``user`` (``user.id``). Поэтому приоритет:

      1. ``chat.id`` — собственно идентификатор чата (main identity для MAX Mini App,
         т.к. на одного пользователя может приходиться несколько чатов с ботом).
      2. ``user.id`` — стандарт Telegram WebApp (MAX также возвращает это поле).
      3. Плоский ``chat_id`` — для нестандартных/legacy-клиентов и локальной отладки.
      4. Запасные плоские поля ``user_id``/``id``.
    """
    chat_obj = _json_object_from_parsed(parsed, "chat")
    cid = chat_obj.get("id")
    if cid is not None:
        s = str(cid).strip()
        if s:
            return s

    user_obj = _user_object_from_parsed(parsed)
    uid = user_obj.get("id")
    if uid is not None:
        s = str(uid).strip()
        if s:
            return s

    direct = (parsed.get("chat_id") or "").strip()
    if direct:
        return direct

    for key in ("user_id", "id"):
        v = (parsed.get(key) or "").strip()
        if v:
            return v

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="В init_data отсутствует идентификатор чата (chat.id / user.id)",
    )


def _extract_name(parsed: dict[str, str], name_hint: str | None) -> str | None:
    """Имя пользователя для сохранения в карточке Mini App.

    Ищем (в порядке приоритета):
      1. Плоские поля ``full_name``/``name``/``first_name`` (если MAX кладёт их наружу).
      2. ``user.first_name`` + ``user.last_name`` из вложенного JSON.
      3. Override от фронта (``name_hint``) — на случай отсутствия имени в init_data.
    """
    for key in ("full_name", "name", "first_name"):
        v = (parsed.get(key) or "").strip()
        if v:
            return v[:255]

    user_obj = _user_object_from_parsed(parsed)
    first = str(user_obj.get("first_name") or "").strip()
    last = str(user_obj.get("last_name") or "").strip()
    composed = " ".join(p for p in (first, last) if p).strip()
    if composed:
        return composed[:255]
    username = str(user_obj.get("username") or "").strip()
    if username:
        return username[:255]

    if name_hint:
        v = name_hint.strip()
        return v[:255] or None
    return None


async def _resolve_org_bot_token(
    session: AsyncSessionDep,
    redis: RedisDep,
    organization_id: UUID,
) -> str:
    """Читает ``MAX_BOT_TOKEN`` из настроек конкретной организации (organization_settings).

    Без fallback на глобальный системный токен: в мультитенанте чужой токен сделает
    подпись «валидной» не для той организации. Если у организации токена нет —
    возвращаем пустую строку, а верификатор выбросит 503.
    """
    repo = PostgresSettingsRepository(session, redis, organization_id=organization_id)
    value = await repo.get_value(sk.MAX_BOT_TOKEN)
    return (value or "").strip()


# --- Dependency: текущий пользователь Mini App --------------------------


async def get_miniapp_user(request: Request, session: AsyncSessionDep) -> MiniAppUserModel:
    """Достаёт MiniAppUserModel по JWT из ``Authorization: Bearer <miniapp>``."""
    auth = request.headers.get("Authorization") or ""
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация Mini App")
    token = auth[7:].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация Mini App")

    settings = get_settings()
    try:
        payload = decode_miniapp_token(token, settings.portal_jwt_secret)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный или просроченный токен Mini App",
        ) from e

    try:
        uid = UUID(str(payload["sub"]))
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный токен Mini App") from e

    stmt = (
        select(MiniAppUserModel)
        .where(MiniAppUserModel.id == uid)
        .options(selectinload(MiniAppUserModel.organization))
    )
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь Mini App не найден")
    if user.organization is None or not user.organization.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Организация отключена")
    return user


MiniAppUserDep = Annotated[MiniAppUserModel, Depends(get_miniapp_user)]


# --- Эндпоинты -----------------------------------------------------------


@router.post("/auth", response_model=MiniAppAuthResponse)
async def miniapp_auth(
    body: MiniAppAuthRequest,
    session: AsyncSessionDep,
    redis: RedisDep,
) -> MiniAppAuthResponse:
    """Авторизация Mini App по ИНН организации и ``init_data`` мессенджера.

    Последовательность:
      1. Находим организацию по ИНН.
      2. Получаем ``MAX_BOT_TOKEN`` из настроек ИМЕННО этой организации.
      3. HMAC-SHA256 верифицируем ``init_data`` (``_verify_init_data_signature``).
      4. Извлекаем ``chat_id``/имя из ПРОВЕРЕННЫХ данных.
      5. Upsert ``MiniAppUserModel`` по (organization_id, chat_id) и выдаём JWT.
    """
    inn = (body.inn or "").strip()
    if not inn:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ИНН не указан")

    # 1) Находим организацию по ИНН
    org = (
        await session.execute(select(OrganizationModel).where(OrganizationModel.inn == inn))
    ).scalar_one_or_none()
    if org is None or not org.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Организация по указанному ИНН не найдена или отключена",
        )

    # 2) Токен бота MAX ТЕКУЩЕЙ организации (без fallback на глобальный — см. _resolve_org_bot_token)
    bot_token = await _resolve_org_bot_token(session, redis, org.id)

    # 3) Криптопроверка init_data — только после этого данным можно доверять
    parsed = await _verify_init_data_signature(body.init_data, bot_token)

    # 4) Извлекаем chat_id и имя из ПРОВЕРЕННЫХ полей
    chat_id = _extract_chat_id(parsed)
    name = _extract_name(parsed, body.name_hint)

    # 5) Upsert MiniAppUserModel по (organization_id, chat_id)
    existing = (
        await session.execute(
            select(MiniAppUserModel).where(
                MiniAppUserModel.organization_id == org.id,
                MiniAppUserModel.chat_id == chat_id,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        user = MiniAppUserModel(
            organization_id=org.id,
            chat_id=chat_id,
            name=name,
        )
        session.add(user)
        await session.flush()
        logger.info("Mini App: создан пользователь org=%s chat_id=%s", org.id, chat_id)
    else:
        user = existing
        if name and name != user.name:
            user.name = name
            session.add(user)

    await session.commit()
    await session.refresh(user)

    settings = get_settings()
    expires = max(1, int(getattr(settings, "portal_jwt_expire_minutes", 60) or 60))
    token = create_miniapp_access_token(
        user_id=user.id,
        organization_id=org.id,
        chat_id=user.chat_id,
        secret=settings.portal_jwt_secret,
        expire_minutes=expires,
    )
    return MiniAppAuthResponse(
        access_token=token,
        expires_in_minutes=expires,
        user_id=user.id,
        organization_id=org.id,
        chat_id=user.chat_id,
        name=user.name,
    )


# --- Admin (портал) ------------------------------------------------------


def _resolve_admin_org_id(actor, override: UUID | None) -> UUID:
    """Org scope для админ-эндпоинтов Mini App.

    super_admin обязан передать ``organization_id`` (query param). Остальные роли —
    только своя организация. Директор/админ организации могут видеть Mini App своей орг-ы.
    """
    if actor.role == ROLE_SUPER_ADMIN:
        if override is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Для супер-админа нужно указать organization_id",
            )
        return override
    if actor.organization_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет организации")
    if override is not None and override != actor.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к другой организации")
    return actor.organization_id


@admin_router.get("/users", response_model=list[MiniAppUserPublic])
async def list_miniapp_users(
    actor: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = None,
) -> list[MiniAppUserPublic]:
    """Список зарегистрированных пользователей Mini App организации (для админа/директора/супер-админа)."""
    if actor.role not in (ROLE_SUPER_ADMIN, ROLE_ORG_ADMIN, ROLE_DIRECTOR):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
    org_id = _resolve_admin_org_id(actor, organization_id)
    rows = (
        await session.execute(
            select(MiniAppUserModel)
            .where(MiniAppUserModel.organization_id == org_id)
            .order_by(MiniAppUserModel.created_at.desc())
        )
    ).scalars().all()
    return [
        MiniAppUserPublic(
            id=u.id,
            chat_id=u.chat_id,
            name=u.name,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )
        for u in rows
    ]


# --- Схемы конфига Mini App (public) -------------------------------------


class MiniAppConfigPage(BaseModel):
    """Страница сайта для клиентского Mini App (без служебных полей)."""

    id: UUID
    title: str
    slug: str
    content: str
    order_index: int


class MiniAppNavItem(BaseModel):
    """Пункт нижнего меню (подпись + slug опубликованной страницы)."""

    label: str
    slug: str


class MiniAppConfigResponse(BaseModel):
    """Единый JSON для отрисовки Mini App организации.

    Состав:
      - идентификаторы организации/сайта,
      - брендинг (title, subtitle, logo_url, theme_color),
      - контакты (произвольный JSONB из карточки сайта),
      - список опубликованных страниц (готов к рендеру в Tabbar).
    """

    organization_id: UUID
    organization_name: str
    organization_display_name: str | None = None
    site_id: UUID
    title: str
    subtitle: str
    logo_url: str | None = None
    theme_color: str
    contacts: dict[str, object]
    pages: list[MiniAppConfigPage]
    nav_items: list[MiniAppNavItem]


# --- Схемы активного сайта (admin) --------------------------------------


class MiniAppActiveSiteRequest(BaseModel):
    """Тело для PUT /portal/miniapp/active-site: ``null`` — сброс привязки."""

    site_id: UUID | None = Field(
        default=None,
        description="UUID сайта организации; null отключает Mini App-рендер сайта",
    )


class MiniAppActiveSiteResponse(BaseModel):
    organization_id: UUID
    active_site_id: UUID | None = None


# --- Публичный эндпоинт: конфиг Mini App по ИНН -------------------------


@public_router.get("/config/{inn}", response_model=MiniAppConfigResponse)
async def get_miniapp_config(inn: str, session: AsyncSessionDep) -> MiniAppConfigResponse:
    """Единая точка получения контента Mini App для клиентского приложения.

    Возвращает настройки активного сайта организации + его опубликованные страницы
    (отсортированные по ``order_index``). Эндпоинт публичный: клиент вызывает его
    ПОСЛЕ авторизации по chat_id, но сам ответ не содержит приватных данных.
    """
    inn_value = (inn or "").strip()
    if not inn_value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ИНН не указан")

    org = (
        await session.execute(select(OrganizationModel).where(OrganizationModel.inn == inn_value))
    ).scalar_one_or_none()
    if org is None or not org.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Организация по указанному ИНН не найдена или отключена",
        )

    if org.active_site_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Для организации не выбран активный сайт Mini App. "
                "Администратор должен указать его в разделе «Приложения»."
            ),
        )

    site = await session.get(SiteModel, org.active_site_id)
    # Дополнительно проверяем, что сайт принадлежит той же организации (защита от
    # рассинхрона, если active_site_id был выставлен на чужой сайт — но проверка на
    # этапе PUT отсечёт такое ещё на входе).
    if site is None or site.organization_id != org.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Активный сайт организации не найден",
        )

    pages_rows = (
        await session.execute(
            select(SitePageModel)
            .where(
                SitePageModel.site_id == site.id,
                SitePageModel.is_published.is_(True),
            )
            .order_by(SitePageModel.order_index.asc(), SitePageModel.created_at.asc())
        )
    ).scalars().all()

    menu_raw = site.menu_items if isinstance(getattr(site, "menu_items", None), list) else None
    nav_dtos = nav_items_for_miniapp(menu_raw, pages_rows)

    return MiniAppConfigResponse(
        organization_id=org.id,
        organization_name=org.name,
        organization_display_name=(org.display_name or "").strip() or None,
        site_id=site.id,
        title=(site.title or "").strip() or org.display_name or org.name,
        subtitle=(site.subtitle or "").strip(),
        logo_url=normalize_site_logo_url((site.logo_url or "").strip() or None),
        theme_color=(site.theme_color or "#000000").strip() or "#000000",
        contacts=dict(site.contacts or {}),
        pages=[
            MiniAppConfigPage(
                id=p.id,
                title=p.title,
                slug=p.slug,
                content=p.content or "",
                order_index=int(p.order_index or 0),
            )
            for p in pages_rows
        ],
        nav_items=[MiniAppNavItem(label=n.label, slug=n.slug) for n in nav_dtos],
    )


# --- Админ: выбор активного сайта Mini App ------------------------------


@admin_router.get("/active-site", response_model=MiniAppActiveSiteResponse)
async def get_miniapp_active_site(
    actor: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = None,
) -> MiniAppActiveSiteResponse:
    """Текущий активный сайт Mini App организации (для отрисовки селекта в UI)."""
    if actor.role not in (ROLE_SUPER_ADMIN, ROLE_ORG_ADMIN, ROLE_DIRECTOR):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
    org_id = _resolve_admin_org_id(actor, organization_id)
    org = await session.get(OrganizationModel, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Организация не найдена")
    return MiniAppActiveSiteResponse(organization_id=org.id, active_site_id=org.active_site_id)


@admin_router.put("/active-site", response_model=MiniAppActiveSiteResponse)
async def set_miniapp_active_site(
    body: MiniAppActiveSiteRequest,
    actor: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = None,
) -> MiniAppActiveSiteResponse:
    """Привязывает выбранный сайт организации к Mini App.

    Доступно: ``super_admin`` (с ``organization_id`` в query), ``org_admin``, ``director``.
    Если указан ``site_id`` — проверяем, что сайт принадлежит этой же организации
    (защита от cross-tenant-утечек).
    """
    if actor.role not in (ROLE_SUPER_ADMIN, ROLE_ORG_ADMIN, ROLE_DIRECTOR):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
    org_id = _resolve_admin_org_id(actor, organization_id)
    org = await session.get(OrganizationModel, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Организация не найдена")

    if body.site_id is None:
        org.active_site_id = None
    else:
        site = await session.get(SiteModel, body.site_id)
        if site is None or site.organization_id != org.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Сайт не найден в вашей организации",
            )
        org.active_site_id = site.id

    session.add(org)
    await session.commit()
    await session.refresh(org)
    return MiniAppActiveSiteResponse(organization_id=org.id, active_site_id=org.active_site_id)


@router.get("/me", response_model=MiniAppMe)
async def miniapp_me(user: MiniAppUserDep) -> MiniAppMe:
    """Текущий пользователь Mini App (по JWT)."""
    org = user.organization
    return MiniAppMe(
        user_id=user.id,
        organization_id=user.organization_id,
        chat_id=user.chat_id,
        name=user.name,
        organization_name=org.name if org else "",
        organization_display_name=(org.display_name or "").strip() or None if org else None,
    )
