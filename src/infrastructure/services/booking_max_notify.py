"""Уведомление сотрудника в MAX о новой онлайн-записи (через бота организации)."""

from __future__ import annotations

import logging

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.infrastructure.models import AppointmentModel, PortalUserModel
from src.infrastructure.repositories import PostgresSettingsRepository
from src.infrastructure.services.max_messenger import MaxMessengerClient

logger = logging.getLogger(__name__)


def _client_name_phone(info: dict) -> tuple[str, str]:
    raw = dict(info or {})
    name = str(raw.get("name") or raw.get("client_name") or "").strip() or "Клиент"
    phone = str(raw.get("phone") or raw.get("tel") or "").strip() or "—"
    return name, phone


async def notify_staff_new_booking(
    *,
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    staff: PortalUserModel,
    appointment: AppointmentModel,
    client_info: dict,
) -> None:
    """Шлёт сообщение в личный чат сотрудника с ботом, если задан ``portal_users.miniapp_chat_id``."""
    raw_chat = (staff.miniapp_chat_id or "").strip()
    if not raw_chat:
        logger.info(
            "Запись создана: у сотрудника %s не задан MAX chat_id в профиле — уведомление не отправлено",
            staff.id,
        )
        return
    try:
        staff_chat_id = int(raw_chat)
    except ValueError:
        logger.warning(
            "Запись: miniapp_chat_id сотрудника %s не целое число, уведомление пропущено",
            staff.id,
        )
        return

    oid = staff.organization_id
    if oid is None:
        return

    repo = PostgresSettingsRepository(session, redis, organization_id=oid)
    client = MaxMessengerClient(
        settings_repository=repo,
        api_base_url=settings.max_api_base,
        platform_api_base_url=settings.max_platform_api_base,
        env_fallback_max_bot_token=None,
    )
    if not (await client.resolve_bot_token()).strip():
        logger.warning(
            "Запись: нет MAX_BOT_TOKEN в настройках организации %s — уведомление сотруднику не отправлено",
            oid,
        )
        return

    tz = settings.app_zoneinfo
    st = appointment.start_time.astimezone(tz)
    en = appointment.end_time.astimezone(tz)
    name, phone = _client_name_phone(client_info)
    text = (
        "Новая запись на приём\n"
        f"Время: {st.strftime('%d.%m.%Y %H:%M')} — {en.strftime('%H:%M')}\n"
        f"Клиент: {name}\n"
        f"Телефон: {phone}\n"
        "Создано через Mini App."
    )
    try:
        await client.send_message(staff_chat_id, text)
        logger.info(
            "Уведомление о новой записи отправлено сотруднику (chat_id=%s, appointment=%s)",
            staff_chat_id,
            appointment.id,
        )
    except Exception:
        logger.exception(
            "Не удалось отправить уведомление о записи в MAX (chat_id=%s, appointment=%s)",
            staff_chat_id,
            appointment.id,
        )
