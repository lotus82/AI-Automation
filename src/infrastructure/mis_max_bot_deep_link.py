"""Deep link /start для регистрации пациента МИС через бота MAX."""

from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

from src.core.config import Settings
from src.domain import system_setting_keys as sk
from src.infrastructure.max_bot_identity import resolve_max_webhook_organization_id
from src.infrastructure.repositories import PostgresSettingsRepository
from src.infrastructure.services.max_messenger import MaxMessengerClient

logger = logging.getLogger(__name__)

_START_CMD = re.compile(r"^/start(?:@[\w.-]+)?(?:\s+(?P<payload>.+))?\s*$", re.IGNORECASE)
_REG_DEEP = re.compile(r"^reg_org_([0-9a-fA-F-]{36})_doc_([0-9a-fA-F-]{36})\s*$")


async def try_max_bot_mis_patient_start_registration(
    body: dict[str, Any],
    *,
    session: Any,
    redis: Any,
    settings: Settings,
    query_organization_id: UUID | None,
) -> dict[str, Any] | None:
    """Обрабатывает ``/start reg_org_<uuid>_doc_<uuid>``: отправляет подсказку и ссылку на Mini App."""
    if (body.get("update_type") or "").strip() != "message_created":
        return None
    msg = body.get("message")
    if not isinstance(msg, dict):
        return None
    sender = msg.get("sender")
    if isinstance(sender, dict) and sender.get("is_bot") is True:
        return None
    recipient = msg.get("recipient")
    if not isinstance(recipient, dict):
        return None
    chat_id = recipient.get("chat_id")
    if chat_id is None:
        return None
    b = msg.get("body")
    if not isinstance(b, dict):
        return None
    text = (b.get("text") or "").strip()
    m = _START_CMD.match(text)
    if not m:
        return None
    arg = (m.group("payload") or "").strip()
    if not arg:
        return None
    m2 = _REG_DEEP.match(arg)
    if not m2:
        return None

    org_id = UUID(m2.group(1))
    doc_id = UUID(m2.group(2))

    org_scope = await resolve_max_webhook_organization_id(
        session,
        body,
        query_organization_id=query_organization_id,
    )
    if org_scope is not None and org_scope != org_id:
        logger.warning(
            "MAX /start МИС: organization_id из deep link %s не совпадает с организацией бота %s",
            org_id,
            org_scope,
        )

    repo = PostgresSettingsRepository(session, redis, organization_id=org_id)
    token = (await repo.get_value(sk.MAX_BOT_TOKEN) or "").strip()
    if not token:
        logger.warning("MAX /start МИС: нет MAX_BOT_TOKEN для organization_id=%s", org_id)
        return {"ok": True, "skipped": True, "reason": "no_max_bot_token"}

    max_client = MaxMessengerClient(
        settings_repository=repo,
        api_base_url=settings.max_api_base,
        platform_api_base_url=settings.max_platform_api_base,
        env_fallback_max_bot_token=settings.max_bot_token,
    )
    payload_token = f"reg_org_{org_id}_doc_{doc_id}"
    base = (settings.mis_max_patient_mini_app_base_url or "").strip()
    lines = [
        "Регистрация в личном кабинете пациента",
        "",
        f"Передайте в мини-приложение параметр startapp / start_param:",
        payload_token,
    ]
    if base:
        sep = "&" if "?" in base else "?"
        lines.extend(["", f"Открыть: {base}{sep}startapp={payload_token}"])
    text_out = "\n".join(lines)
    try:
        await max_client.send_message(int(chat_id), text_out)
    except Exception:
        logger.exception("MAX /start МИС: ошибка отправки в chat_id=%s", chat_id)
        # 200 + ok, чтобы платформа не долбила повторными вебхуками
        return {"ok": True, "mis_patient_start": False, "send_error": True}
    return {"ok": True, "mis_patient_start": True}
