"""Вебхук мессенджера MAX: доставка текста в ``ProcessTextMessageUseCase`` (тот же сценарий, что голос/чат).

События входящего VoIP (**``parse_max_voice_call_incoming``**) обрабатываются отдельно: фоновая задача **фаза 23**
(**``run_max_inbound_call_background``** — задержка, ``answer_call``, Pipecat).
Имя отправителя (если есть в JSON MAX) передаётся в сценарий как ``user_name`` для подстановки в системный промпт (фаза 20).
При вызове ``search_web`` сначала отправляется промежуточное сообщение в чат, затем итоговый ответ (фаза 21).
Групповые чаты: до сценария применяется фильтр упоминания (**``apply_max_group_mention_rules``**).
CORS настраивается глобально в ``CORSMiddleware`` (``main.py``).

Организация определяется по ``recipient.user_id`` бота (в т.ч. в событиях VoIP: корень, ``call`` / ``voice_call``),
см. ``MAX_BOT_USER_ID`` после сохранения ``MAX_BOT_TOKEN``. Опционально: ``?organization_id=`` в URL.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query

from src.api.dependencies import (
    AsyncSessionDep,
    RedisDep,
    SettingsDep,
    build_process_text_message_use_case,
)
from src.infrastructure.max_bot_identity import resolve_max_webhook_organization_id
from src.infrastructure.repositories import PostgresSettingsRepository
from src.infrastructure.services.max_incoming_group import apply_max_group_mention_rules
from src.infrastructure.mis_max_bot_patient_reg_flow import try_max_bot_mis_patient_registration_flow
from src.infrastructure.services.max_messenger import (
    MaxMessengerClient,
    parse_max_voice_call_incoming,
    parse_max_webhook_incoming,
)

router = APIRouter(prefix="/max", tags=["max"])
logger = logging.getLogger(__name__)


@router.post("/webhook")
async def max_messenger_webhook(
    body: dict[str, Any],
    session: AsyncSessionDep,
    redis: RedisDep,
    settings: SettingsDep,
    organization_id: UUID | None = Query(
        None,
        description="Принудительно: id организации; иначе определяется по получателю сообщения (бот)",
    ),
) -> dict[str, Any]:
    """Принимает JSON от MAX; ``chat_id`` → ``session_id`` в Redis; ответ уходит через ``MaxMessengerClient``."""
    parsed_call = parse_max_voice_call_incoming(body)
    if parsed_call is not None:
        call_id, user_label = parsed_call
        org_scope = await resolve_max_webhook_organization_id(
            session,
            body,
            query_organization_id=organization_id,
        )

        async def _voip_webhook_bg() -> None:
            from src.infrastructure.voice.max_call_session import run_max_inbound_call_background

            await run_max_inbound_call_background(
                call_id=call_id,
                user_label=user_label,
                redis=redis,
                settings=settings,
                organization_id=org_scope,
            )

        asyncio.create_task(_voip_webhook_bg())
        logger.info(
            "Вебхук MAX: событие входящего VoIP, call_id=%s, org=%s",
            call_id,
            org_scope,
        )
        return {"ok": True, "call": "accepted_pipeline_scheduled"}

    start_reg = await try_max_bot_mis_patient_registration_flow(
        body,
        session=session,
        redis=redis,
        settings=settings,
        query_organization_id=organization_id,
    )
    if start_reg is not None:
        return start_reg

    parsed = parse_max_webhook_incoming(body)
    if parsed is None:
        # Неизвестное событие — отвечаем 200, чтобы платформа не долбила повторными доставками.
        ut = (body.get("update_type") or "").strip()
        logger.debug("Вебхук MAX: пропуск после parse (update_type=%s)", ut or "?")
        return {"ok": True, "skipped": True}

    org_scope = await resolve_max_webhook_organization_id(
        session,
        body,
        query_organization_id=organization_id,
    )
    settings_repo = PostgresSettingsRepository(session, redis, organization_id=org_scope)
    use_case = build_process_text_message_use_case(session, redis, settings, organization_id=org_scope)
    max_client = MaxMessengerClient(
        settings_repository=settings_repo,
        api_base_url=settings.max_api_base,
        platform_api_base_url=settings.max_platform_api_base,
        env_fallback_max_bot_token=settings.max_bot_token,
    )

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

    async def on_intermediate(msg: str) -> None:
        """Сразу уведомляет пользователя MAX до выполнения веб-поиска (фаза 21)."""
        await max_client.send_message(chat_id, msg)

    voice_audio: list[bytes] = []

    async def on_voice_generated(data: bytes) -> None:
        """Передаёт WAV итогового ответа; отправка в чат — после текста (фаза 22)."""
        voice_audio.append(data)

    try:
        reply = await use_case.execute(
            processed,
            session_id,
            interaction_user_label=user_label,
            user_name=user_label,
            append_text_messenger_system_supplement=True,
            on_intermediate_message=on_intermediate,
            on_voice_generated=on_voice_generated,
        )
        await max_client.send_message(chat_id, reply)
        if voice_audio:
            try:
                await max_client.send_voice_message(chat_id, voice_audio[0])
            except Exception:
                logger.exception(
                    "MAX вебхук: не удалось отправить голосовое вложение, chat_id=%s",
                    chat_id,
                )
    except Exception:
        logger.exception("Сбой обработки вебхука MAX (chat_id=%s)", chat_id)
        # Повторная доставка MAX не решит ошибку LLM/CRM; фиксируем 200 после лога.
        return {"ok": False}

    return {"ok": True}
