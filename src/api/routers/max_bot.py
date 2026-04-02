"""Вебхук мессенджера MAX: доставка текста в ``ProcessTextMessageUseCase`` (тот же сценарий, что голос/чат).

CORS для симулятора вебхука с фронтенда настраивается глобально в ``CORSMiddleware`` (``main.py``):
разрешены все источники — ``POST /api/max/webhook`` доступен с той же панели (``bots.html``).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from src.api.dependencies import MaxMessengerClientDep, ProcessTextMessageUseCaseDep
from src.infrastructure.services.max_messenger import parse_max_webhook_incoming

router = APIRouter(prefix="/max", tags=["max"])
logger = logging.getLogger(__name__)


@router.post("/webhook")
async def max_messenger_webhook(
    body: dict[str, Any],
    use_case: ProcessTextMessageUseCaseDep,
    max_client: MaxMessengerClientDep,
) -> dict[str, Any]:
    """Принимает JSON от MAX; ``chat_id`` → ``session_id`` в Redis; ответ уходит через ``MaxMessengerClient``."""
    parsed = parse_max_webhook_incoming(body)
    if parsed is None:
        # Неизвестное событие — отвечаем 200, чтобы платформа не долбила повторными доставками.
        return {"ok": True, "skipped": True}

    chat_id, user_text, user_label = parsed
    session_id = str(chat_id)
    logger.info(
        "Вебхук MAX: обработка message_created/callback, chat_id=%s, len(text)=%s",
        chat_id,
        len(user_text),
    )

    try:
        reply = await use_case.execute(
            user_text,
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
