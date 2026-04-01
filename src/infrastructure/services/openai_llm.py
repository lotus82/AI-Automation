"""Адаптер LLM на официальном async-клиенте OpenAI."""

from __future__ import annotations

import json
import re

from openai import AsyncOpenAI

from src.core.config import Settings
from src.use_cases.interfaces import ILLMService, LLMToolCall

_CHAT_MODEL = "gpt-4o-mini"

# Системный промпт на английском — так модель обычно стабильнее следует роли.
SALES_CONSULTANT_SYSTEM_PROMPT = (
    "You are a professional sales consultant representing a supplier of industrial machinery "
    "from China. Your clients are Russian businesses. You answer clearly, politely, and "
    "factually, using only the provided knowledge base context when it contains relevant "
    "prices or specifications. If the context is insufficient, say so honestly and suggest "
    "what information would be needed. Respond in the same language as the customer's "
    "message when possible (Russian for Russian queries)."
)

# Дополнение для вызова инструмента record_lead (используется в ProcessTextMessageUseCase).
SALES_TOOLS_INSTRUCTION_RU = (
    "\n\nЕсли клиент явно оставил номер телефона и согласие на обратную связь, "
    "вызови инструмент record_lead с полями phone, name (имя или компания), notes (краткий контекст). "
    "После успешной передачи контактов в CRM ответь по-русски одним коротким подтверждением."
)

_COACH_SYSTEM_TEMPLATE = """Ты — тренер по продажам (Sales Coach). Менеджер отрабатывал навыки в диалоге с ИИ, который изображал клиента.
В транскрипте роль **user** — реплики менеджера по продажам, роль **assistant** — реплики ИИ-клиента.

Оцени работу МЕНЕДЖЕРА (user) по шкале 1–10: насколько грамотно отработаны возражения и логика ведения диалога.

Название сценария: {title}

Ожидаемые возражения и линии, которые менеджер должен был отработать:
{objections}

Верни СТРОГО один JSON-объект без пояснений вокруг:
{{"score": <целое от 1 до 10>, "recommendations": "<3–6 предложений на русском: сильные стороны и что улучшить>"}}
Если диалога почти не было — поставь низкий балл и объясни почему."""

_QA_SYSTEM_PROMPT = """Ты — руководитель отдела контроля качества (ОКК) в B2B-продажах промышленного оборудования.
Проанализируй полный текст диалога между клиентом и ИИ-консультантом.
Верни СТРОГО один JSON-объект без пояснений вокруг него, формата:
{"score": <целое число от 1 до 10>, "recommendations": "<2-5 предложений на русском: что улучшить ассистенту>"}
Критерии: вежливость, точность по фактам, уместность RAG, работа с возражениями, призыв к следующему шагу.
Если диалог пустой или слишком короткий, поставь низкий балл и объясни почему."""


class OpenAILLMService(ILLMService):
    """Генерация ответа консультанта через OpenAI Chat Completions."""

    def __init__(self, settings: Settings) -> None:
        # TODO: Добавить явную валидацию OPENAI_API_KEY и обработку rate limit/сетевых сбоев;
        #       при отсутствии ключа возвращается текст-заглушка для разработки без вызова API.
        self._client: AsyncOpenAI | None = None
        if settings.openai_api_key:
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def generate_response(
        self,
        prompt: str,
        context: list[str],
        *,
        history: list[dict] | None = None,
        system_prompt: str | None = None,
    ) -> str:
        if not self._client:
            hist_note = f" (в истории {len(history or [])} сообщ.)" if history else ""
            return (
                "[Режим без API-ключа] Задайте переменную окружения OPENAI_API_KEY, "
                "чтобы получить ответ от языковой модели. Сейчас это заглушка для локальных тестов."
                f"{hist_note}"
            )

        if context:
            context_block = "\n\n---\n\n".join(context)
            user_content = (
                "Ниже фрагменты из внутренней базы знаний (прайсы и описания оборудования):\n\n"
                f"{context_block}\n\n"
                f"Текущий вопрос клиента:\n{prompt}"
            )
        else:
            user_content = (
                "В базе знаний не найдено близких по смыслу документов для этого запроса. "
                "Ответь как консультант, честно указав отсутствие данных в базе.\n\n"
                f"Текущий вопрос клиента:\n{prompt}"
            )

        system = (system_prompt or "").strip() or SALES_CONSULTANT_SYSTEM_PROMPT
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        if history:
            for turn in history:
                role = turn.get("role")
                content = turn.get("content")
                if role in ("user", "assistant") and isinstance(content, str) and content.strip():
                    messages.append({"role": role, "content": content.strip()})
        messages.append({"role": "user", "content": user_content})

        completion = await self._client.chat.completions.create(
            model=_CHAT_MODEL,
            messages=messages,
        )
        choice = completion.choices[0].message.content
        return (choice or "").strip()

    async def generate_sales_response_with_tools(
        self,
        messages: list[dict],
        *,
        tools: list[dict],
    ) -> tuple[str | None, list[LLMToolCall]]:
        if not self._client:
            return (
                "[Режим без API-ключа] Инструменты CRM недоступны без OPENAI_API_KEY.",
                [],
            )

        kwargs: dict = {"model": _CHAT_MODEL, "messages": messages}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        completion = await self._client.chat.completions.create(**kwargs)
        msg = completion.choices[0].message
        text = msg.content
        raw_calls = msg.tool_calls or []
        out: list[LLMToolCall] = []
        for tc in raw_calls:
            fn = tc.function
            try:
                args = json.loads(fn.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            out.append(
                LLMToolCall(
                    tool_call_id=tc.id,
                    name=fn.name,
                    arguments=args,
                )
            )
        return text, out

    async def analyze_conversation_quality(self, transcript_text: str) -> tuple[int, str]:
        if not self._client:
            return (
                0,
                "Анализ ОКК недоступен: задайте OPENAI_API_KEY на воркере Celery.",
            )

        completion = await self._client.chat.completions.create(
            model=_CHAT_MODEL,
            messages=[
                {"role": "system", "content": _QA_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Текст диалога (user/assistant по порядку):\n\n{transcript_text}",
                },
            ],
            response_format={"type": "json_object"},
        )
        raw = completion.choices[0].message.content or "{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}", raw)
            data = json.loads(m.group(0)) if m else {}
        score = int(data.get("score", 1))
        score = max(1, min(10, score))
        rec = str(data.get("recommendations", "")).strip() or "Рекомендации не сформулированы."
        return score, rec

    async def analyze_training_performance(
        self,
        transcript_text: str,
        *,
        scenario_title: str,
        objections_to_raise: str,
    ) -> tuple[int, str]:
        if not self._client:
            return (
                0,
                "Оценка тренера недоступна: задайте OPENAI_API_KEY на воркере Celery.",
            )

        system = _COACH_SYSTEM_TEMPLATE.format(
            title=scenario_title.strip() or "—",
            objections=objections_to_raise.strip() or "—",
        )
        completion = await self._client.chat.completions.create(
            model=_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": f"Текст диалога (user = менеджер, assistant = ИИ-клиент):\n\n{transcript_text}",
                },
            ],
            response_format={"type": "json_object"},
        )
        raw = completion.choices[0].message.content or "{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}", raw)
            data = json.loads(m.group(0)) if m else {}
        score = int(data.get("score", 1))
        score = max(1, min(10, score))
        rec = str(data.get("recommendations", "")).strip() or "Обратная связь не сформулирована."
        return score, rec
