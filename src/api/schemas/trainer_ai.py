"""REST-схемы ИИ-тренера (ответы FastAPI). Модели BANT/MEDDIC — в domain.trainer_ai_schemas."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from src.domain.trainer_ai_schemas import BantAnalysisResult, MeddicAnalysisResult

__all__ = [
    "BantAnalysisResult",
    "MeddicAnalysisResult",
    "TrainerMethodologyPublic",
    "TrainerAnalyzeRequest",
    "TrainerAnalyzeResponse",
    "TrainerSimulateRequest",
    "TrainerSimulateResponse",
]


class TrainerMethodologyPublic(BaseModel):
    id: UUID
    code: str
    name: str
    description: str


class TrainerAnalyzeRequest(BaseModel):
    transcript: str = Field(..., min_length=1, description="Текст транскрипта диалога")
    methodology_code: Literal["bant", "meddic"] = Field(
        default="bant",
        description="Код методики",
    )
    manager_id: str | None = Field(
        default=None,
        description="Идентификатор менеджера для учёта в ai_trainer_sessions",
    )


class TrainerAnalyzeResponse(BaseModel):
    methodology: str
    bant: BantAnalysisResult | None = None
    meddic: MeddicAnalysisResult | None = None
    saved_session_id: UUID | None = Field(
        default=None,
        description="id строки ai_trainer_sessions после сохранения",
    )


class TrainerSimulateRequest(BaseModel):
    manager_phone: str = Field(..., min_length=1, description="Добавочный номер или SIP-суффикс")
    scenario_id: UUID = Field(..., description="Сценарий тренажёра (персона клиента)")


class TrainerSimulateResponse(BaseModel):
    status: Literal["initiated", "error"] = "initiated"
    session_id: str = Field(..., description="UUID сессии диалога")
    channel_id: str | None = Field(default=None, description="ARI channel id")
    message: str = ""
