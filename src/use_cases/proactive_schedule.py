"""Проактивная отправка в MAX по расписанию: RAG, ``generate_response``, история чата, мониторинг."""

from __future__ import annotations

import json
import logging

from src.core.config import llm_system_time_prefix
from src.core.utils.text_cleaner import remove_markdown
from src.domain import system_setting_keys as sk
from src.domain.system_roles import get_default_consultant_prompt
from src.domain.default_system_prompts import FALLBACK_DEFAULT_CONSULTANT_PROMPT
from src.domain.entities import Schedule, ScheduledEvent
from src.use_cases.interfaces import (
    IChatMemoryRepository,
    IChatMonitoringPublisher,
    IEmbeddingService,
    IKnowledgeRepository,
    ILLMService,
    IProactiveDeliveryMessenger,
    ISettingsRepository,
)

logger = logging.getLogger(__name__)


class ExecuteProactiveScheduleUseCase:
    """Формирует ответ через LLM + базу знаний и отправляет текст в чат MAX."""

    def __init__(
        self,
        embedding_service: IEmbeddingService,
        knowledge_repository: IKnowledgeRepository,
        llm_service: ILLMService,
        chat_memory: IChatMemoryRepository,
        settings_repository: ISettingsRepository,
        chat_monitoring: IChatMonitoringPublisher,
        messenger: IProactiveDeliveryMessenger,
    ) -> None:
        self._embeddings = embedding_service
        self._knowledge = knowledge_repository
        self._llm = llm_service
        self._memory = chat_memory
        self._settings_repo = settings_repository
        self._monitor = chat_monitoring
        self._messenger = messenger

    async def _context_message_limit(self) -> int:
        raw = (await self._settings_repo.get_value(sk.MAX_CONTEXT_LIMIT) or "").strip()
        if not raw:
            return 10
        try:
            n = int(raw)
        except ValueError:
            return 10
        return max(1, min(n, 200))

    async def execute(
        self,
        schedule: Schedule,
        *,
        event: ScheduledEvent | None = None,
    ) -> None:
        """Генерирует текст, отправляет в ``chat_id`` расписания, пишет пару реплик в память чата."""
        session_id = schedule.chat_id.strip()
        parts: list[str] = []
        ct = (schedule.content_template or "").strip()
        if ct:
            parts.append(ct)
        if event is not None:
            payload = json.dumps(event.event_data or {}, ensure_ascii=False)
            parts.append(f"Данные события (JSON):\n{payload}")
        user_for_rag = "\n\n".join(parts) if parts else "Сформируй короткое проактивное сообщение для чата."

        base = (await get_default_consultant_prompt(self._settings_repo)).strip() or FALLBACK_DEFAULT_CONSULTANT_PROMPT
        extra = (schedule.prompt or "").strip()
        if extra:
            full_system = f"{base}\n\n--- Инструкции расписания ---\n\n{extra}"
        else:
            full_system = base

        full_system = llm_system_time_prefix() + full_system

        embedding = await self._embeddings.generate_embedding(user_for_rag)
        items = await self._knowledge.search_similar(embedding, limit=3)
        context_chunks: list[str] = []
        for item in items:
            chunk_parts = [item.title]
            if (item.description or "").strip():
                chunk_parts.append(item.description.strip())
            chunk_parts.append(item.content)
            context_chunks.append("\n".join(chunk_parts))

        ctx_limit = await self._context_message_limit()
        history = await self._memory.get_history(session_id, limit=ctx_limit)

        reply = await self._llm.generate_response(
            user_for_rag,
            context_chunks,
            history=history,
            system_prompt=full_system,
        )
        reply = remove_markdown((reply or "").strip())
        if not reply:
            logger.warning("Расписание: пустой ответ LLM, chat_id=%s", session_id)
            return

        await self._messenger.send_plain_text(schedule.chat_id, reply)

        await self._memory.save_message(
            session_id,
            "user",
            user_for_rag,
            user_display="Расписание",
        )
        await self._monitor.publish_new_message(
            session_id=session_id,
            role="user",
            content=user_for_rag,
            user_info="Расписание",
        )
        await self._memory.save_message(session_id, "assistant", reply)
        await self._monitor.publish_new_message(
            session_id=session_id,
            role="assistant",
            content=reply,
            user_info="Расписание",
        )

        logger.info(
            "Расписание: сообщение отправлено chat_id=%s тип=%s длина_ответа=%s",
            session_id,
            schedule.type.value,
            len(reply),
        )
