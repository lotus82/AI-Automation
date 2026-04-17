"""Сценарии текстового чата с RAG."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

from redis.asyncio import Redis

from src.core.config import Settings, llm_system_time_prefix
from src.core.llm_chat_messages import memory_history_to_openai_messages
from src.core.utils.text_cleaner import remove_markdown
from src.domain.default_system_prompts import FALLBACK_DEFAULT_CONSULTANT_PROMPT
from src.domain import system_setting_keys as sk
from src.domain.system_roles import get_effective_consultant_prompt, get_max_group_additional_prompt
from src.use_cases.interfaces import (
    IChatMemoryRepository,
    IChatMonitoringPublisher,
    ICRMService,
    IEmbeddingService,
    IKnowledgeRepository,
    ILLMService,
    IMaxVoiceSynthesizer,
    ISearchService,
    ISettingsRepository,
)

# Дополнение к системному промпту для вызова инструмента record_lead.
SALES_TOOLS_INSTRUCTION_RU = (
    "\n\nЕсли клиент явно оставил номер телефона и согласие на обратную связь, "
    "вызови инструмент record_lead с полями phone, name (имя или компания), notes (краткий контекст). "
    "После успешной передачи контактов в CRM ответь по-русски одним коротким подтверждением."
)

# Инструкция для инструмента веб-поиска (фаза 19).
WEB_SEARCH_TOOL_INSTRUCTION_RU = (
    "\n\nЕсли для ответа нужны актуальные сведения из открытого интернета (новости, статистика, "
    "общедоступные факты), а во внутренней базе знаний недостаточно данных, вызови инструмент "
    "search_web с полем query (краткий поисковый запрос). После получения сниппетов сформируй ответ "
    "самостоятельно, по-русски, без выдумывания источников."
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

# Инструмент веб-поиска (DuckDuckGo, публичные сниппеты).
_SEARCH_WEB_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "search_web",
        "description": (
            "Используй этот инструмент для поиска актуальной информации в интернете "
            "(новости, статистика, факты), если не знаешь ответа."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Поисковый запрос (ключевые слова)",
                },
            },
            "required": ["query"],
        },
    },
}

_MAX_TOOL_ROUNDS = 6

# Дословно из ТЗ фазы 20; не дублируем, если строка уже есть в промпте из БД / FALLBACK / миграции 017.
_LAST_MESSAGE_FOCUS_MARKER = "very last message from the user"
_LAST_MESSAGE_FOCUS_RULE_EN = (
    "\n\nFocus ONLY on answering the very last message from the user. "
    "Do not re-answer or summarize previous questions from the chat history."
)

# Дополнение к промпту консультанта (фаза 21); не дублируем, если уже есть в БД / FALLBACK / миграции 019.
_GROUNDING_MARKER_RU = "никогда не выдумывай факты"
_GROUNDING_RULE_RU = (
    "\n\nНикогда не выдумывай факты, которых нет в базе знаний или в результатах поиска. "
    "Если не уверен — скажи, что не знаешь."
)

# Текст промежуточного сообщения при вызове search_web (текстовые каналы; голос задаёт свой вариант).
_DEFAULT_SEARCH_PENDING_MESSAGE = "Подождите, ищу информацию в интернете..."

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
        search_service: ISearchService,
        redis_client: Redis | None = None,
        app_settings: Settings | None = None,
        *,
        chat_monitoring_organization_id: UUID | None = None,
    ) -> None:
        self._embeddings = embedding_service
        self._knowledge = knowledge_repository
        self._llm = llm_service
        self._memory = chat_memory
        self._crm = crm_service
        self._settings_repo = settings_repository
        self._monitor = chat_monitoring
        self._monitor_org_id = chat_monitoring_organization_id
        self._search = search_service
        self._redis = redis_client
        self._app_settings = app_settings
        self._max_voice_synth_cache: IMaxVoiceSynthesizer | None = None
        self._max_voice_synth_resolved = False

    async def _maybe_append_max_group_prompt(self, session_id: str, system_text: str) -> str:
        """Дополнительный фрагмент для группы MAX (после базового промпта роли и CRM)."""
        extra = await get_max_group_additional_prompt(self._settings_repo, session_id)
        if not extra:
            return system_text
        return f"{system_text}\n\n---\n\n{extra}"

    async def _web_search_enabled(self) -> bool:
        """Читает ENABLE_WEB_SEARCH; по умолчанию True, если ключа ещё нет в БД."""
        raw = (await self._settings_repo.get_value(sk.ENABLE_WEB_SEARCH) or "").strip().lower()
        if not raw:
            return True
        return raw not in ("0", "false", "no", "off")

    async def _max_voice_reply_enabled(self) -> bool:
        """Читает MAX_VOICE_REPLY_ENABLED; по умолчанию выключено, если ключа нет в БД."""
        raw = (await self._settings_repo.get_value(sk.MAX_VOICE_REPLY_ENABLED) or "").strip().lower()
        if not raw:
            return False
        return raw in ("1", "true", "yes", "on")

    async def _get_max_voice_synthesizer(self) -> IMaxVoiceSynthesizer | None:
        """Ленивая сборка SaluteSpeech для озвучки MAX (нужны Redis и Settings процесса)."""
        if self._max_voice_synth_resolved:
            return self._max_voice_synth_cache
        self._max_voice_synth_resolved = True
        if not self._redis or not self._app_settings:
            return None
        from src.infrastructure.services.max_voice_synthesis import create_salute_max_voice_synthesizer

        self._max_voice_synth_cache = await create_salute_max_voice_synthesizer(
            self._settings_repo,
            self._redis,
            self._app_settings,
        )
        return self._max_voice_synth_cache

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
        user_name: str | None = None,
        append_text_messenger_system_supplement: bool = False,
        on_intermediate_message: Callable[[str], Awaitable[None]] | None = None,
        intermediate_search_message: str | None = None,
        on_voice_generated: Callable[[bytes], Awaitable[None]] | None = None,
        client_timezone_id: str | None = None,
    ) -> str:
        """История (лимит из MAX_CONTEXT_LIMIT) → RAG → LLM → запись в Redis и PostgreSQL → мониторинг WS.

        ``user_name`` — опционально (например из MAX); усиливает персонализацию в системном промпте.
        История в LLM передаётся списком сообщений с ролями, не одной строкой.
        ``on_intermediate_message`` — опционально: например мгновенная отправка текста в MAX или TTS до веб-поиска.
        ``on_voice_generated`` — если включено **MAX_VOICE_REPLY_ENABLED**, после итогового ответа передаётся WAV (SaluteSpeech).
        """
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
            consultant_base = await get_effective_consultant_prompt(self._settings_repo, session_id=session_id)
            if not consultant_base:
                consultant_base = FALLBACK_DEFAULT_CONSULTANT_PROMPT
            system_text = consultant_base + (SALES_TOOLS_INSTRUCTION_RU if use_crm_tools else "")

        include_web_tool = (not skip_rag) and (await self._web_search_enabled())
        if include_web_tool:
            system_text += WEB_SEARCH_TOOL_INSTRUCTION_RU

        system_text = await self._maybe_append_max_group_prompt(session_id, system_text)

        if append_text_messenger_system_supplement:
            supplement = (await self._settings_repo.get_value(sk.TEXT_BOT_SYSTEM_SUPPLEMENT) or "").strip()
            if supplement:
                system_text = f"{system_text}\n\n---\n\n{supplement}"

        system_text = llm_system_time_prefix(client_timezone_id) + system_text

        un = (user_name or "").strip()
        if un:
            system_text += (
                f"\nСистемная информация: Имя собеседника - {un}. "
                "Если это уместно и диалог только начинается, обращайся к нему по имени. "
                "Не нужно повторять имя в каждом сообщении."
            )

        if _LAST_MESSAGE_FOCUS_MARKER.lower() not in system_text.lower():
            system_text += _LAST_MESSAGE_FOCUS_RULE_EN

        if _GROUNDING_MARKER_RU not in system_text.lower():
            system_text += _GROUNDING_RULE_RU

        history_messages = memory_history_to_openai_messages(history)
        messages: list[dict] = [{"role": "system", "content": system_text}]
        messages.extend(history_messages)
        messages.append({"role": "user", "content": user_content})

        tools: list[dict] = []
        if use_crm_tools:
            tools.append(_RECORD_LEAD_TOOL)
        if include_web_tool:
            tools.append(_SEARCH_WEB_TOOL)

        final_reply = ""

        for _ in range(_MAX_TOOL_ROUNDS):
            text, tool_calls = await self._llm.generate_sales_response_with_tools(
                messages,
                tools=tools,
            )
            if not tool_calls:
                final_reply = (text or "").strip()
                break

            if on_intermediate_message and any(tc.name == "search_web" for tc in tool_calls):
                pending_txt = (
                    (intermediate_search_message or _DEFAULT_SEARCH_PENDING_MESSAGE).strip()
                    or _DEFAULT_SEARCH_PENDING_MESSAGE
                )
                try:
                    await on_intermediate_message(pending_txt)
                except Exception:
                    logger.exception(
                        "Не удалось отправить промежуточное уведомление о веб-поиске; сценарий продолжается"
                    )

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
                elif tc.name == "search_web":
                    sq = str(tc.arguments.get("query", "")).strip()
                    try:
                        result_text = await self._search.search(sq, max_results=3)
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("Сбой ISearchService.search")
                        result_text = f"Ошибка поиска: {exc!s}"
                    payload = result_text
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

        # Один канал текста для БД, MAX и TTS: без Markdown (DeepSeek и др. часто вставляют **, #, `).
        final_reply = remove_markdown(final_reply)

        label = (interaction_user_label or "").strip() or None
        await self._memory.save_message(
            session_id, "user", user_text, user_display=label
        )
        await self._monitor.publish_new_message(
            session_id=session_id,
            role="user",
            content=user_text,
            user_info=label,
            organization_id=self._monitor_org_id,
        )
        await self._memory.save_message(session_id, "assistant", final_reply)
        await self._monitor.publish_new_message(
            session_id=session_id,
            role="assistant",
            content=final_reply,
            user_info=label,
            organization_id=self._monitor_org_id,
        )

        if (
            await self._max_voice_reply_enabled()
            and on_voice_generated is not None
            and final_reply.strip()
        ):
            synth = await self._get_max_voice_synthesizer()
            if synth is not None:
                try:
                    audio = await synth.synthesize_to_file(final_reply)
                    if audio:
                        await on_voice_generated(audio)
                except Exception:
                    logger.exception(
                        "Сбой синтеза голосового ответа MAX (SaluteSpeech); текстовый ответ уже сохранён"
                    )

        logger.info(
            "Текстовый ответ сохранён: session_id=%s, длина ответа=%s",
            session_id,
            len(final_reply),
        )
        return final_reply
