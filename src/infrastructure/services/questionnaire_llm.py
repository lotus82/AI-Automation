"""ИИ-оценка заполненного опросника (DeepSeek / OpenAI через настройки панели)."""

from __future__ import annotations

import json

from src.infrastructure.services.dynamic_llm import DynamicLLMService

_SYSTEM = """Ты — эксперт по анализу ответов в корпоративных опросниках.
Пользователь заполнил опрос; ниже даны критерии оценки и структурированные ответы с набранными баллами (где применимо).
Дай развёрнутый профессиональный вердикт на русском: сильные стороны, пробелы, рекомендации.
Не выдумывай факты, опирайся только на переданные данные."""


class QuestionnaireLLMService(DynamicLLMService):
    async def assess_answers(
        self,
        *,
        criteria: str,
        answers_for_llm: list[dict],
    ) -> str:
        client, model = await self._client_and_model()
        if not client:
            msg = "Задайте API-ключ LLM в настройках панели (DeepSeek или OpenAI)."
            raise RuntimeError(msg)

        user_content = (
            "Оцени ответы согласно правилам и критериям ниже.\n\n"
            f"Критерии и правила оценки:\n{criteria.strip() or '(не заданы — оцени по здравому смыслу)'}\n\n"
            "Ответы респондента (JSON):\n"
            f"{json.dumps(answers_for_llm, ensure_ascii=False, indent=2)}"
        )

        completion = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
        )
        return (completion.choices[0].message.content or "").strip()
