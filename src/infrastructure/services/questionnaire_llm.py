"""ИИ-оценка заполненного опросника (DeepSeek / OpenAI через настройки панели)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from src.infrastructure.services.dynamic_llm import DynamicLLMService

_SYSTEM = """Ты — эксперт по анализу ответов в корпоративных опросниках.
Пользователь заполнил опрос; ниже даны критерии оценки и структурированные ответы с набранными баллами (где применимо).
Дай развёрнутый профессиональный вердикт на русском: сильные стороны, пробелы, рекомендации.
Не выдумывай факты, опирайся только на переданные данные."""


def _build_system_message(output_format_supplement: str) -> str:
    sup = (output_format_supplement or "").strip()
    if not sup:
        return _SYSTEM
    return f"{_SYSTEM}\n\n---\n\n{sup}"


class QuestionnaireLLMService(DynamicLLMService):
    def _user_content(self, *, criteria: str, answers_for_llm: list[dict]) -> str:
        return (
            "Оцени ответы согласно правилам и критериям ниже.\n\n"
            f"Критерии и правила оценки:\n{criteria.strip() or '(не заданы — оцени по здравому смыслу)'}\n\n"
            "Ответы респондента (JSON):\n"
            f"{json.dumps(answers_for_llm, ensure_ascii=False, indent=2)}"
        )

    async def assess_answers(
        self,
        *,
        criteria: str,
        answers_for_llm: list[dict],
        output_format_supplement: str = "",
    ) -> str:
        client, model = await self._client_and_model()
        if not client:
            msg = "Задайте API-ключ LLM в настройках панели (DeepSeek или OpenAI)."
            raise RuntimeError(msg)

        user_content = self._user_content(criteria=criteria, answers_for_llm=answers_for_llm)
        system = _build_system_message(output_format_supplement)

        completion = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
        )
        return (completion.choices[0].message.content or "").strip()

    async def assess_answers_stream(
        self,
        *,
        criteria: str,
        answers_for_llm: list[dict],
        output_format_supplement: str = "",
    ) -> AsyncIterator[str]:
        client, model = await self._client_and_model()
        if not client:
            msg = "Задайте API-ключ LLM в настройках панели (DeepSeek или OpenAI)."
            raise RuntimeError(msg)

        user_content = self._user_content(criteria=criteria, answers_for_llm=answers_for_llm)
        system = _build_system_message(output_format_supplement)

        stream = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
            stream=True,
        )
        async for chunk in stream:
            choice = chunk.choices[0] if chunk.choices else None
            if choice is None:
                continue
            delta = choice.delta
            piece = (delta.content or "") if delta else ""
            if piece:
                yield piece
