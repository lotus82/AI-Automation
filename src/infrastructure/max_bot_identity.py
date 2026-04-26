"""Идентификация бота MAX для маршрутизации вебхука и long poll по организациям."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any
from uuid import UUID

import httpx
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.domain import system_setting_keys as sk
from src.infrastructure.models import OrganizationSettingModel, SystemSettingModel
from src.infrastructure.repositories import PostgresSettingsRepository

logger = logging.getLogger(__name__)


def _user_id_from_recipient_dict(recipient: Any) -> int | None:
    if not isinstance(recipient, dict):
        return None
    for key in ("user_id", "id"):
        raw = recipient.get(key)
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                continue
    return None


def extract_recipient_bot_user_id_from_max_update(body: Any) -> int | None:
    """Идентификатор бота MAX: ``message.recipient``, корневой ``recipient``, блок ``call`` / ``voice_call``."""
    if not isinstance(body, dict):
        return None
    msg = body.get("message")
    if isinstance(msg, dict):
        uid = _user_id_from_recipient_dict(msg.get("recipient"))
        if uid is not None:
            return uid
    uid = _user_id_from_recipient_dict(body.get("recipient"))
    if uid is not None:
        return uid
    for block_name in ("call", "voice_call", "voiceCall"):
        block = body.get(block_name)
        if isinstance(block, dict):
            uid = _user_id_from_recipient_dict(block.get("recipient"))
            if uid is not None:
                return uid
            uid = _user_id_from_recipient_dict(block.get("callee"))
            if uid is not None:
                return uid
    return None


async def resolve_max_webhook_organization_id(
    session: AsyncSession,
    body: dict[str, Any],
    *,
    query_organization_id: UUID | None,
) -> UUID | None:
    """Организация для вебхука (текст, VoIP): явный query, иначе ``recipient.user_id`` ↔ ``MAX_BOT_USER_ID``."""
    if query_organization_id is not None:
        return query_organization_id

    bot_uid = extract_recipient_bot_user_id_from_max_update(body)
    if bot_uid is None:
        return None

    uid_str = str(bot_uid)
    stmt = select(OrganizationSettingModel.organization_id).where(
        OrganizationSettingModel.key == sk.MAX_BOT_USER_ID,
        OrganizationSettingModel.value == uid_str,
    )
    matches = list((await session.scalars(stmt)).all())
    if len(matches) > 1:
        logger.error(
            "MAX вебхук: несколько организаций с MAX_BOT_USER_ID=%s — используйте уникальные боты",
            uid_str,
        )
    if len(matches) >= 1:
        return matches[0]

    row = await session.get(SystemSettingModel, sk.MAX_BOT_USER_ID)
    if row is not None and (row.value or "").strip() == uid_str:
        return None

    logger.warning(
        "MAX вебхук: recipient user_id=%s не сопоставлен ни с одной организацией (сохраните токен в настройках)",
        uid_str,
    )
    return None


async def fetch_max_bot_user_id_from_api(token: str, *, platform_api_base: str) -> int | None:
    """``GET {platform}/me`` с заголовком ``Authorization: <token>``."""
    t = (token or "").strip()
    if not t:
        return None
    url = f"{(platform_api_base or '').rstrip('/')}/me"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(url, headers={"Authorization": t})
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.warning("MAX GET /me не удался (%s): %s", url, exc)
        return None
    if not isinstance(data, dict):
        return None
    raw = data.get("user_id")
    if raw is None:
        raw = data.get("id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


async def store_max_bot_user_id(
    session: AsyncSession,
    redis: Redis,
    *,
    organization_id: UUID | None,
    user_id: int,
) -> None:
    repo = PostgresSettingsRepository(session, redis, organization_id=organization_id)
    await repo.upsert_values({sk.MAX_BOT_USER_ID: str(int(user_id))})


async def sync_max_bot_user_id_for_token(
    session: AsyncSession,
    redis: Redis,
    *,
    organization_id: UUID | None,
    token: str,
    platform_api_base: str,
) -> None:
    """После смены ``MAX_BOT_USER_ID`` вызывает API и обновляет настройки."""
    uid = await fetch_max_bot_user_id_from_api(token, platform_api_base=platform_api_base)
    if uid is None:
        return
    await store_max_bot_user_id(session, redis, organization_id=organization_id, user_id=uid)
    logger.info(
        "MAX: сохранён %s=%s для organization_id=%s",
        sk.MAX_BOT_USER_ID,
        uid,
        organization_id,
    )


async def sync_all_max_bot_user_ids_from_stored_tokens(
    session: AsyncSession,
    redis: Redis,
    *,
    app_settings: Settings,
) -> None:
    """При старте приложения: для каждого сохранённого токена подтянуть ``user_id`` бота (если ещё нет)."""
    base = app_settings.max_platform_api_base
    stmt_sys = select(SystemSettingModel.value).where(SystemSettingModel.key == sk.MAX_BOT_TOKEN)
    gtok = await session.scalar(stmt_sys)
    g = (gtok or "").strip()
    if g:
        row = await session.get(SystemSettingModel, sk.MAX_BOT_USER_ID)
        if row is None or not (row.value or "").strip():
            await sync_max_bot_user_id_for_token(session, redis, organization_id=None, token=g, platform_api_base=base)

    stmt_org = select(OrganizationSettingModel.organization_id, OrganizationSettingModel.value).where(
        OrganizationSettingModel.key == sk.MAX_BOT_TOKEN,
    )
    for oid, val in (await session.execute(stmt_org)).all():
        t = (val or "").strip()
        if not t:
            continue
        row = await session.get(
            OrganizationSettingModel,
            {"organization_id": oid, "key": sk.MAX_BOT_USER_ID},
        )
        if row is not None and (row.value or "").strip():
            continue
        await sync_max_bot_user_id_for_token(session, redis, organization_id=oid, token=t, platform_api_base=base)


async def enumerate_max_bot_long_poll_org_ids(session: AsyncSession) -> list[UUID | None]:
    """Список ``organization_id`` для отдельного long poll (по одному на уникальный ``MAX_BOT_TOKEN``).

    ``None`` — глобальный токен из ``system_settings``. При совпадении токена у глобальных и организации
    остаётся вариант организации (последняя при обходе строк БД).
    """
    by_token: dict[str, UUID | None] = {}

    gval = await session.scalar(select(SystemSettingModel.value).where(SystemSettingModel.key == sk.MAX_BOT_TOKEN))
    g = (gval or "").strip()
    if g:
        by_token[g] = None

    stmt_org = select(OrganizationSettingModel.organization_id, OrganizationSettingModel.value).where(
        OrganizationSettingModel.key == sk.MAX_BOT_TOKEN,
    )
    for oid, val in (await session.execute(stmt_org)).all():
        t = (val or "").strip()
        if not t:
            continue
        prev = by_token.get(t)
        if prev is not None and prev != oid:
            logger.warning(
                "Одинаковый MAX_BOT_TOKEN у организаций %s и %s — long poll один на токен, контекст последней",
                prev,
                oid,
            )
        by_token[t] = oid

    return list(by_token.values())


async def resolve_max_long_poll_bot_token(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    organization_id: UUID | None,
) -> str:
    """То же, что ``MaxMessengerClient._resolve_bot_token`` — избежать рассинхрона с long poll.

    ``organization_id=None`` — область system_settings, иначе organization_settings. Fallback — ``.env`` ``MAX_BOT_TOKEN``.
    """
    repo = PostgresSettingsRepository(session, redis, organization_id=organization_id)
    db = (await repo.get_value(sk.MAX_BOT_TOKEN) or "").strip()
    if db:
        return db
    return (settings.max_bot_token or "").strip()


async def deduplicate_max_long_poll_targets(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    candidates: list[UUID | None],
) -> list[UUID | None]:
    """
    Схлопывает воркеры, если фактически один и тот же бот: ``enumerate`` смотрит только
    сырые строки в ``organization_settings`` / ``system_settings``, тогда как при старте
    токен может дублироваться через ``.env`` (глобальная область = токен из env, у орг. —
    тот же в БД) → в списке целей два id, в рантайме — одинаковый ``Authorization`` и
    дубли ответа в /updates.
    """
    if len(candidates) < 2:
        return candidates

    groups: defaultdict[str, list[UUID | None]] = defaultdict(list)
    for oid in candidates:
        t = (await resolve_max_long_poll_bot_token(session, redis, settings, oid)).strip()
        if not t:
            t = f"__unconfigured_token__:{oid if oid is not None else 'global'}"
        groups[t].append(oid)

    out: list[UUID | None] = []
    for t, oids in groups.items():
        chosen = next((o for o in oids if o is not None), None)
        out.append(chosen)
        if len(oids) > 1:
            show = t[-4:] if len(t) >= 4 and not t.startswith("__unconfigured") else t
            logger.info(
                "MAX long poll: схлопывание: resolved «%s» → org_id=%s, кандидаты %s",
                show,
                chosen,
                oids,
            )
    return out
