"""Вебхук мессенджера MAX: доставка текста в ``ProcessTextMessageUseCase`` (тот же сценарий, что голос/чат).

Групповые чаты: до сценария применяется фильтр упоминания (**``apply_max_group_mention_rules``**).
CORS настраивается глобально в ``CORSMiddleware`` (``main.py``).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from src.api.dependencies import (
    MaxMessengerClientDep,
    ProcessTextMessageUseCaseDep,
    SettingsRepositoryDep,
)
from src.infrastructure.services.max_incoming_group import apply_max_group_mention_rules
from src.infrastructure.services.max_messenger import parse_max_webhook_incoming

router = APIRouter(prefix="/max", tags=["max"])
logger = logging.getLogger(__name__)


@router.post("/webhook")
async def max_messenger_webhook(
    body: dict[str, Any],
    use_case: ProcessTextMessageUseCaseDep,
    max_client: MaxMessengerClientDep,
    settings_repo: SettingsRepositoryDep,
) -> dict[str, Any]:
    """Принимает JSON от MAX; ``chat_id`` → ``session_id`` в Redis; ответ уходит через ``MaxMessengerClient``."""
    parsed = parse_max_webhook_incoming(body)
    if parsed is None:
        # Неизвестное событие — отвечаем 200, чтобы платформа не долбила повторными доставками.
        ut = (body.get("update_type") or "").strip()
        logger.debug("Вебхук MAX: пропуск после parse (update_type=%s)", ut or "?")
        return {"ok": True, "skipped": True}

    chat_id, user_text, user_label, is_group = parsed
    processed = await apply_max_group_mention_rules(
        settings_repo,
        raw_user_text=user_text,
        is_group_chat=is_group,
    )
    if processed is None:
        logger.info(
            "Вебхук MAX: пропуск (группа без упоминания бота или пустой текст), chat_id=%s",
            chat_id,
        )
        return {"ok": True, "skipped": True, "reason": "group_no_mention_or_empty"}

    session_id = str(chat_id)
    logger.info(
        "Вебхук MAX: обработка message_created/callback, chat_id=%s, len(text)=%s, group=%s",
        chat_id,
        len(processed),
        is_group,
    )

    try:
        reply = await use_case.execute(
            processed,
            session_id,
            interaction_user_label=user_label,
            append_text_messenger_system_supplement=True,
        )
        await max_client.send_message(chat_id, reply)
    except Exception:
        logger.exception("Сбой обработки вебхука MAX (chat_id=%s)", chat_id)
        # Повторная доставка MAX не решит ошибку LLM/CRM; фиксируем 200 после лога.
        return {"ok": False}

    return {"ok": True}
