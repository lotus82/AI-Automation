"""ИИ-тренер: разбор транскриптов по BANT/MEDDIC через DeepSeek/OpenAI (JSON mode)."""

from __future__ import annotations

import json
import logging
import re

from src.domain.trainer_ai_schemas import BantAnalysisResult, MeddicAnalysisResult
from src.infrastructure.services.dynamic_llm import DynamicLLMService

logger = logging.getLogger(__name__)

_BANT_SYSTEM = """Ты — эксперт по B2B-продажам и методике BANT (Budget, Authority, Need, Timeline).
Проанализируй транскрипт диалога между менеджером по продажам и клиентом.

Верни СТРОГО один JSON-объект без текста вокруг, со ключами:
"budget", "authority", "need", "timeline", "recommendation" — все значения строки на русском.

Правила:
- Если бюджет (Budget) в диалоге не выявлен, в поле budget укажи «не выявлено» или кратко почему.
- Если роль ЛПР / полномочия (Authority) не ясны, в authority укажи «не выявлено».
- В need опиши выявленные боли; если мало данных — укажи пробелы.
- В timeline — сроки или «не выявлено».
- В recommendation дай конкретные советы менеджеру на следующий контакт.
- ОБЯЗАТЕЛЬНО: если поля authority или budget по сути «не выявлено», в recommendation включи хотя бы один конкретный вопрос,
  который менеджер должен задать клиенту в следующем звонке (формулировка вопроса дословно)."""

_MEDDIC_SYSTEM = """Ты — эксперт по B2B и методике MEDDIC (Metrics, Economic buyer, Decision criteria, Decision process, Identify pain, Champion).
Проанализируй транскрипт диалога менеджера с клиентом.

Верни СТРОГО один JSON-объект с ключами на английском:
"metrics", "economic_buyer", "decision_criteria", "decision_process", "identify_pain", "champion", "recommendation".
Все значения — строки на русском.

В recommendation — советы и конкретные вопросы на следующий звонок, если информации по какому-либо элементу MEDDIC недостаточно."""


def _parse_json_object(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return {}
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return {}
    return data if isinstance(data, dict) else {}


class TrainerAIService(DynamicLLMService):
    """Анализ транскриптов для панели «ИИ-тренер»; клиент LLM — как у DynamicLLMService."""

    async def analyze_transcript(
        self,
        transcript: str,
        methodology: str,
    ) -> BantAnalysisResult | MeddicAnalysisResult:
        client, model = await self._client_and_model()
        if not client:
            msg = "Задайте API-ключ DeepSeek или OpenAI в настройках панели."
            raise RuntimeError(msg)

        meth = (methodology or "bant").strip().lower()
        if meth == "meddic":
            system = _MEDDIC_SYSTEM
            cls = MeddicAnalysisResult
        else:
            system = _BANT_SYSTEM
            cls = BantAnalysisResult

        completion = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": f"Транскрипт диалога:\n\n{transcript.strip()}",
                },
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        raw = completion.choices[0].message.content or "{}"
        data = _parse_json_object(raw)
        try:
            return cls.model_validate(data)
        except Exception:
            logger.warning("Trainer AI: validate failed, raw keys=%s", list(data.keys()))
            raise
