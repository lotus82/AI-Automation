"""Сценарии текстового чата с RAG."""

from __future__ import annotations

import json
import logging

from src.domain.default_system_prompts import FALLBACK_DEFAULT_CONSULTANT_PROMPT
from src.domain import system_setting_keys as sk
from src.use_cases.interfaces import (
    IChatMemoryRepository,
    IChatMonitoringPublisher,
    ICRMService,
    IEmbeddingService,
    IKnowledgeRepository,
    ILLMService,
    ISettingsRepository,
)

# Дополнение к системному промпту для вызова инструмента record_lead.
SALES_TOOLS_INSTRUCTION_RU = (
    "\n\nЕсли клиент явно оставил номер телефона и согласие на обратную связь, "
    "вызови инструмент record_lead с полями phone, name (имя или компания), notes (краткий контекст). "
    "После успешной передачи контактов в CRM ответь по-русски одним коротким подтверждением."
)

# Инструмент передачи лида в CRM (OpenAI tools schema).
_RECORD_LEAD_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "record_lead",
        "description": (
            "Зафиксировать контакт клиента для менеджера: телефон, имя, заметки. "
            "Вызывай только когда клиент явно оставил телефон и согласен на связь."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "phone": {
                    "type": "string",
                    "description": "Номер телефона, как указал клиент",
                },
                "name": {
                    "type": "string",
                    "description": "Имя контакта или компания",
                },
                "notes": {
                    "type": "string",
                    "description": "Краткий контекст запроса (опционально)",
                },
            },
            "required": ["phone", "name"],
        },
    },
}

_MAX_TOOL_ROUNDS = 4

logger = logging.getLogger(__name__)


class ProcessTextMessageUseCase:
    """Обработка текстового сообщения: память → эмбеддинг → RAG → LLM (+CRM) → сохранение реплик."""

    def __init__(
        self,
        embedding_service: IEmbeddingService,
        knowledge_repository: IKnowledgeRepository,
        llm_service: ILLMService,
        chat_memory: IChatMemoryRepository,
        crm_service: ICRMService,
        settings_repository: ISettingsRepository,
        chat_monitoring: IChatMonitoringPublisher,
    ) -> None:
        self._embeddings = embedding_service
        self._knowledge = knowledge_repository
        self._llm = llm_service
        self._memory = chat_memory
        self._crm = crm_service
        self._settings_repo = settings_repository
        self._monitor = chat_monitoring

    async def _maybe_append_max_group_prompt(self, session_id: str, system_text: str) -> str:
        """Если ``session_id`` совпадает с **MAX_GROUP_CHAT_ID**, добавляет **MAX_GROUP_ADDITIONAL_PROMPT**."""
        configured = (await self._settings_repo.get_value(sk.MAX_GROUP_CHAT_ID) or "").strip()
        if not configured or session_id.strip() != configured:
            return system_text
        extra = (await self._settings_repo.get_value(sk.MAX_GROUP_ADDITIONAL_PROMPT) or "").strip()
        if not extra:
            return system_text
        return f"{system_text}\n\n---\n\n{extra}"

    async def _context_message_limit(self) -> int:
        raw = (await self._settings_repo.get_value(sk.MAX_CONTEXT_LIMIT) or "").strip()
        if not raw:
            return 10
        try:
            n = int(raw)
        except ValueError:
            return 10
        return max(1, min(n, 200))

    def _build_user_content(self, prompt: str, context_chunks: list[str]) -> str:
        if context_chunks:
            context_block = "\n\n---\n\n".join(context_chunks)
            return (
                "Ниже фрагменты из внутренней базы знаний (прайсы и описания оборудования):\n\n"
                f"{context_block}\n\n"
                f"Текущий вопрос клиента:\n{prompt}"
            )
        return (
            "В базе знаний не найдено близких по смыслу документов для этого запроса. "
            "Ответь как консультант, честно указав отсутствие данных в базе.\n\n"
            f"Текущий вопрос клиента:\n{prompt}"
        )

    async def execute(
        self,
        message: str,
        session_id: str,
        *,
        system_prompt_override: str | None = None,
        use_crm_tools: bool = True,
        skip_rag: bool = False,
        interaction_user_label: str | None = None,
        append_text_messenger_system_supplement: bool = False,
    ) -> str:
        """История (лимит из MAX_CONTEXT_LIMIT) → RAG → LLM → запись в Redis и PostgreSQL → мониторинг WS."""
        user_text = message.strip()
        logger.info(
            "Текстовое сообщение: session_id=%s, длина текста=%s, skip_rag=%s",
            session_id,
            len(user_text),
            skip_rag,
        )

        ctx_limit = await self._context_message_limit()
        history = await self._memory.get_history(session_id, limit=ctx_limit)

        if skip_rag:
            context_chunks: list[str] = []
            user_content = (
                "Ниже реплика менеджера по продажам. Ответь в своей роли (клиент), продолжая диалог.\n\n"
                f"{user_text}"
            )
        else:
            embedding = await self._embeddings.generate_embedding(user_text)
            items = await self._knowledge.search_similar(embedding, limit=3)
            context_chunks = []
            for item in items:
                parts = [item.title]
                if (item.description or "").strip():
                    parts.append(item.description.strip())
                parts.append(item.content)
                context_chunks.append("\n".join(parts))
            user_content = self._build_user_content(user_text, context_chunks)

        if (system_prompt_override or "").strip():
            system_text = system_prompt_override.strip()
            if use_crm_tools:
                system_text += SALES_TOOLS_INSTRUCTION_RU
        else:
            db_prompt = (await self._settings_repo.get_value(sk.DEFAULT_CONSULTANT_PROMPT) or "").strip()
            consultant_base = db_prompt or FALLBACK_DEFAULT_CONSULTANT_PROMPT
            system_text = consultant_base + (SALES_TOOLS_INSTRUCTION_RU if use_crm_tools else "")

        system_text = await self._maybe_append_max_group_prompt(session_id, system_text)

        if append_text_messenger_system_supplement:
            supplement = (await self._settings_repo.get_value(sk.TEXT_BOT_SYSTEM_SUPPLEMENT) or "").strip()
            if supplement:
                system_text = f"{system_text}\n\n---\n\n{supplement}"

        messages: list[dict] = [{"role": "system", "content": system_text}]
        for turn in history:
            role = turn.get("role")
            content = turn.get("content")
            if role in ("user", "assistant") and isinstance(content, str) and content.strip():
                messages.append({"role": role, "content": content.strip()})
        messages.append({"role": "user", "content": user_content})

        tools = [_RECORD_LEAD_TOOL] if use_crm_tools else []
        final_reply = ""

        for _ in range(_MAX_TOOL_ROUNDS):
            text, tool_calls = await self._llm.generate_sales_response_with_tools(
                messages,
                tools=tools,
            )
            if not tool_calls:
                final_reply = (text or "").strip()
                break

            openai_tool_calls = []
            for tc in tool_calls:
                openai_tool_calls.append(
                    {
                        "id": tc.tool_call_id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                        },
                    }
                )
            messages.append(
                {
                    "role": "assistant",
                    "content": text or "",
                    "tool_calls": openai_tool_calls,
                }
            )

            for tc in tool_calls:
                if tc.name == "record_lead":
                    phone = str(tc.arguments.get("phone", "")).strip()
                    name = str(tc.arguments.get("name", "")).strip()
                    notes = str(tc.arguments.get("notes", "")).strip() or user_text[:2000]
                    try:
                        lead_id = await self._crm.create_lead(phone, name, notes)
                        payload = json.dumps(
                            {"ok": True, "lead_id": lead_id},
                            ensure_ascii=False,
                        )
                    except Exception as exc:  # noqa: BLE001 — отдаём модели текст ошибки
                        payload = json.dumps(
                            {"ok": False, "error": str(exc)},
                            ensure_ascii=False,
                        )
                else:
                    payload = json.dumps(
                        {"ok": False, "error": f"Неизвестный инструмент: {tc.name}"},
                        ensure_ascii=False,
                    )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.tool_call_id,
                        "content": payload,
                    }
                )
        else:
            final_reply = (
                final_reply
                or "Прошу прощения, не удалось завершить обработку запроса. Попробуйте ещё раз."
            )

        label = (interaction_user_label or "").strip() or None
        await self._memory.save_message(
            session_id, "user", user_text, user_display=label
        )
        await self._monitor.publish_new_message(
            session_id=session_id,
            role="user",
            content=user_text,
            user_info=label,
        )
        await self._memory.save_message(session_id, "assistant", final_reply)
        await self._monitor.publish_new_message(
            session_id=session_id,
            role="assistant",
            content=final_reply,
            user_info=label,
        )

        logger.info(
            "Текстовый ответ сохранён: session_id=%s, длина ответа=%s",
            session_id,
            len(final_reply),
        )
        return final_reply
