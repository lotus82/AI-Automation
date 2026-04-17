"""Схемы API модуля МИС."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from src.api.schemas.questionnaires import AssessAnswerItem, QuestionnairePublic


class MedicalDoctorCreate(BaseModel):
    portal_user_id: UUID
    qualification: str = ""


class MedicalDoctorOut(BaseModel):
    id: UUID
    organization_id: UUID
    portal_user_id: UUID
    qualification: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    display_name: str | None = None


class MedicalPatientCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=512)
    phone: str = ""
    birth_date: date | None = None
    gender: str | None = Field(default=None, max_length=32)
    height: float | None = None
    weight: float | None = None
    current_diagnosis: str = ""
    treatment_plan: str = ""


class MedicalPatientAdminCreate(MedicalPatientCreate):
    """Создание пациента админом организации (назначение на выбранного врача МИС)."""

    doctor_id: UUID


class MedicalPatientUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=512)
    phone: str | None = None
    birth_date: date | None = None
    gender: str | None = Field(default=None, max_length=32)
    height: float | None = None
    weight: float | None = None
    current_diagnosis: str | None = None
    treatment_plan: str | None = None


class MedicalPatientPortalSelfUpdate(BaseModel):
    """Поля карты, которые пациент может менять сам (личный кабинет MAX)."""

    full_name: str | None = Field(default=None, min_length=1, max_length=512)
    phone: str | None = None
    birth_date: date | None = None
    height: float | None = None
    weight: float | None = None


class MedicalPatientOut(BaseModel):
    id: UUID
    organization_id: UUID
    doctor_id: UUID
    full_name: str
    phone: str
    birth_date: date | None
    gender: str | None
    height: float | None
    weight: float | None
    current_diagnosis: str
    treatment_plan: str
    max_chat_id: str | None = Field(
        default=None,
        description="Числовой id чата с ботом в MAX (заполняется при регистрации через бота)",
    )
    created_at: datetime
    updated_at: datetime


class MedicalEntryCreate(BaseModel):
    type: Literal["exam", "survey"]
    entry_date: date
    data: dict[str, Any] = Field(default_factory=dict)
    conclusion: str = ""
    recommendations: str = ""


class MedicalEntryOut(BaseModel):
    id: UUID
    patient_id: UUID
    type: str
    entry_date: date
    data: dict[str, Any]
    conclusion: str
    recommendations: str
    created_at: datetime


class PublicPatientCardResponse(BaseModel):
    patient: MedicalPatientOut
    entries: list[MedicalEntryOut]


class MisAiConsultRequest(BaseModel):
    patient_id: UUID
    question: str = Field(..., min_length=1, max_length=8000)


class MisAiConsultResponse(BaseModel):
    answer: str


class PublicHealthDiaryCreate(BaseModel):
    """Запись дневника здоровья от пациента (публично по UUID карты)."""

    entry_date: date
    metric: str = Field(..., min_length=1, max_length=200)
    value: str = Field(..., min_length=1, max_length=2000)


class MisMaxSendRequest(BaseModel):
    """Отправка текстовой сводки по пациенту в чат MAX (тот же транспорт, что у уведомлений магазина)."""

    max_chat_id: int = Field(..., description="Числовой chat_id в MAX")


class MisSendQuestionnaireRequest(BaseModel):
    """Ссылка на опросник для пациента через бота MAX организации."""

    questionnaire_id: UUID
    max_chat_id: int | None = Field(
        default=None,
        description="Если не указан — используется max_chat_id из карты пациента (диалог с ботом при регистрации в MAX)",
    )


class MisQuestionnaireInviteInfo(BaseModel):
    """Публичные данные для прохождения опроса по приглашению врача."""

    questionnaire: QuestionnairePublic
    patient_label: str = Field(description="Краткая подпись без раскрытия лишних данных")


class MisQuestionnaireInviteSubmitBody(BaseModel):
    token: str = Field(..., min_length=32)
    answers: list[AssessAnswerItem]


class MisQuestionnaireInviteSubmitResponse(BaseModel):
    analysis: str
    saved: bool = True
