"""LLM через динамические настройки: DeepSeek (по умолчанию) или OpenAI, async OpenAI SDK."""

from __future__ import annotations

import json
import logging
import re

from openai import AsyncOpenAI

from src.core.config import Settings, llm_system_time_prefix
from src.core.llm_chat_messages import memory_history_to_openai_messages
from src.domain.default_system_prompts import FALLBACK_ANALYST_QA_PROMPT
from src.domain import system_setting_keys as sk
from src.domain.system_roles import get_analyst_prompt, get_default_consultant_prompt
from src.use_cases.interfaces import ILLMService, ISettingsRepository, LLMToolCall

_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
_DEEPSEEK_CHAT_MODEL = "deepseek-chat"
_OPENAI_CHAT_MODEL = "gpt-4o-mini"

logger = logging.getLogger(__name__)

# Шаблон тренера: поля сценария подставляются из БД тренажёра (не из system_settings).
_COACH_SYSTEM_TEMPLATE = """Ты — тренер по продажам (Sales Coach). Менеджер отрабатывал навыки в диалоге с ИИ, который изображал клиента.
В транскрипте роль **user** — реплики менеджера по продажам, роль **assistant** — реплики ИИ-клиента.

Оцени работу МЕНЕДЖЕРА (user) по шкале 1–10: насколько грамотно отработаны возражения и логика ведения диалога.

Название сценария: {title}

Ожидаемые возражения и линии, которые менеджер должен был отработать:
{objections}

Верни СТРОГО один JSON-объект без пояснений вокруг:
{{"score": <целое от 1 до 10>, "recommendations": "<3–6 предложений на русском: сильные стороны и что улучшить>"}}
Если диалога почти не было — поставь низкий балл и объясни почему."""


class DynamicLLMService(ILLMService):
    """Чат и аналитика: провайдер и ключи читаются из **ISettingsRepository** (кэш Redis в репозитории)."""

    def __init__(self, settings: Settings, settings_repo: ISettingsRepository) -> None:
        self._settings = settings
        self._repo = settings_repo
        self._client: AsyncOpenAI | None = None
        self._client_sig: str = ""

    async def _build_client(self) -> tuple[AsyncOpenAI | None, str, str]:
        """Возвращает (клиент или None, имя модели чата, подпись для кэша клиента)."""
        raw_provider = await self._repo.get_value(sk.LLM_PROVIDER)
        provider = (raw_provider or "deepseek").strip().lower()
        if provider not in ("deepseek", "openai"):
            provider = "deepseek"

        if provider == "deepseek":
            key = (await self._repo.get_value(sk.DEEPSEEK_API_KEY) or "").strip()
            if not key and self._settings.deepseek_api_key:
                key = self._settings.deepseek_api_key.strip()
            sig = f"deepseek:{key[:12]}:{len(key)}"
            if not key:
                return None, _DEEPSEEK_CHAT_MODEL, sig
            client = AsyncOpenAI(api_key=key, base_url=_DEEPSEEK_BASE_URL)
            return client, _DEEPSEEK_CHAT_MODEL, sig

        key = (await self._repo.get_value(sk.OPENAI_API_KEY) or "").strip()
        if not key and self._settings.openai_api_key:
            key = self._settings.openai_api_key.strip()
        sig = f"openai:{key[:12]}:{len(key)}"
        if not key:
            return None, _OPENAI_CHAT_MODEL, sig
        return AsyncOpenAI(api_key=key), _OPENAI_CHAT_MODEL, sig

    async def _client_and_model(self) -> tuple[AsyncOpenAI | None, str]:
        client, model, sig = await self._build_client()
        if client is None:
            self._client = None
            self._client_sig = ""
            return None, model
        if sig != self._client_sig:
            self._client = client
            self._client_sig = sig
        return self._client, model

    async def _resolve_chat_temperature(self) -> float:
        """Температура для диалога консультанта и ``generate_response`` (ключ **LLM_TEMPERATURE**, 0.0–1.0)."""
        raw = (await self._repo.get_value(sk.LLM_TEMPERATURE) or "").strip().replace(",", ".")
        if not raw:
            return 0.2
        try:
            t = float(raw)
        except ValueError:
            return 0.2
        return max(0.0, min(1.0, t))

    async def generate_response(
        self,
        prompt: str,
        context: list[str],
        *,
        history: list[dict] | None = None,
        system_prompt: str | None = None,
        client_timezone_id: str | None = None,
    ) -> str:
        client, model = await self._client_and_model()
        if not client:
            return (
                "[Нет API-ключа] Задайте DEEPSEEK_API_KEY или OPENAI_API_KEY в разделе «Настройки» панели "
                "(или выберите провайдера OpenAI и ключ OpenAI)."
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

        db_system = (await get_default_consultant_prompt(self._repo)).strip()
        system = (system_prompt or "").strip() or db_system or (
            "You are a helpful B2B sales assistant. Reply in the user's language when possible."
        )
        supplement = (await self._repo.get_value(sk.TEXT_BOT_SYSTEM_SUPPLEMENT) or "").strip()
        if supplement:
            system = f"{system}\n\n---\n\n{supplement}"
        system = llm_system_time_prefix(client_timezone_id) + system
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        if history:
            messages.extend(memory_history_to_openai_messages(history))
        messages.append({"role": "user", "content": user_content})

        temperature = await self._resolve_chat_temperature()
        completion = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        choice = completion.choices[0].message.content
        return (choice or "").strip()

    async def generate_sales_response_with_tools(
        self,
        messages: list[dict],
        *,
        tools: list[dict],
    ) -> tuple[str | None, list[LLMToolCall]]:
        """Передаёт ``messages`` в API как список объектов чата (system / user / assistant / tool).

        Историю диалога нельзя склеивать в одну строку: каждая реплика — отдельное сообщение с полем ``role``.
        Первый элемент обычно ``role=system`` (см. ``ProcessTextMessageUseCase``; группы MAX — фаза 17).
        """
        client, model = await self._client_and_model()
        if not client:
            return (
                "[Нет API-ключа] Укажите ключи в панели «Настройки» для выбранного LLM-провайдера.",
                [],
            )

        temperature = await self._resolve_chat_temperature()
        kwargs: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        logger.info(
            "LLM (продажи + инструменты): model=%s, temperature=%s, сообщений в запросе=%s, инструментов=%s",
            model,
            temperature,
            len(messages),
            len(tools),
        )
        completion = await client.chat.completions.create(**kwargs)
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
        client, model = await self._client_and_model()
        if not client:
            return (
                0,
                "ОКК недоступен: задайте API-ключ выбранного провайдера в настройках панели.",
            )

        qa_prompt = (await get_analyst_prompt(self._repo)).strip()
        system_content = llm_system_time_prefix(None) + (qa_prompt or FALLBACK_ANALYST_QA_PROMPT)

        completion = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_content},
                {
                    "role": "user",
                    "content": f"Текст диалога (user/assistant по порядку):\n\n{transcript_text}",
                },
            ],
            temperature=0.0,
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
        client, model = await self._client_and_model()
        if not client:
            return (
                0,
                "Оценка тренера недоступна: задайте API-ключ в настройках панели.",
            )

        system = _COACH_SYSTEM_TEMPLATE.format(
            title=scenario_title.strip() or "—",
            objections=objections_to_raise.strip() or "—",
        )
        system = llm_system_time_prefix(None) + system
        completion = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": f"Текст диалога (user = менеджер, assistant = ИИ-клиент):\n\n{transcript_text}",
                },
            ],
            temperature=0.0,
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
