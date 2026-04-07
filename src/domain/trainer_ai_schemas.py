"""Pydantic-модели разбора транскриптов (BANT / MEDDIC) для LLM JSON и валидации."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BantAnalysisResult(BaseModel):
    """Результат разбора транскрипта по BANT (JSON из LLM)."""

    budget: str = Field(
        ...,
        description="Статус выявления бюджета: что сказал клиент или «не выявлено».",
    )
    authority: str = Field(
        ...,
        description="Роль ЛПР и вовлечённость: кто принимает решение или «не выявлено».",
    )
    need: str = Field(
        ...,
        description="Выявленные боли и потребности клиента; если нет — кратко указать пробел.",
    )
    timeline: str = Field(
        ...,
        description="Сроки и этапы закупки, озвученные в диалоге или «не выявлено».",
    )
    recommendation: str = Field(
        ...,
        description=(
            "Совет менеджеру на следующий контакт. Если Authority или Budget не выявлены, "
            "обязательно сформулируй конкретный вопрос, который менеджер должен задать."
        ),
    )


class MeddicAnalysisResult(BaseModel):
    """Результат разбора по MEDDIC."""

    metrics: str = Field(..., description="M — метрики успеха, KPI, измеримые цели.")
    economic_buyer: str = Field(..., description="E — экономический покупатель и бюджет.")
    decision_criteria: str = Field(..., description="DD — критерии выбора поставщика.")
    decision_process: str = Field(..., description="D — процесс принятия решения, этапы.")
    identify_pain: str = Field(..., description="I — выявленная боль и срочность.")
    champion: str = Field(..., description="C — внутренний чемпион сделки.")
    recommendation: str = Field(
        ...,
        description="Рекомендации менеджеру и конкретные вопросы на следующий звонок.",
    )
