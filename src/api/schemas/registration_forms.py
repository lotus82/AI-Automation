"""Схемы конструктора форм регистрации и мероприятий."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

FormFieldType = Literal[
    "short_text",
    "long_text",
    "phone",
    "email",
    "number",
    "date",
    "single_choice",
    "multiple_choice",
]


class FormFieldSchema(BaseModel):
    id: str = Field(..., min_length=1, max_length=64)
    type: FormFieldType
    label: str = Field(..., min_length=1, max_length=512)
    required: bool = False
    placeholder: str | None = Field(default=None, max_length=512)
    options: list[str] = Field(default_factory=list)
    order: int = Field(default=0, ge=0, le=10_000)

    @field_validator("options", mode="before")
    @classmethod
    def _strip_options(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("options должен быть списком строк")
        out: list[str] = []
        for x in v:
            s = str(x).strip()
            if s:
                out.append(s)
        return out

    @model_validator(mode="after")
    def _choice_options(self) -> FormFieldSchema:
        if self.type in ("single_choice", "multiple_choice") and len(self.options) < 1:
            raise ValueError(f"Поле «{self.label}»: для выбора нужен хотя бы один вариант")
        return self


class FormTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=512)
    description: str = ""
    fields: list[FormFieldSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> FormTemplateCreate:
        ids = [f.id for f in self.fields]
        if len(ids) != len(set(ids)):
            raise ValueError("Идентификаторы полей (id) должны быть уникальны")
        return self


class FormTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=512)
    description: str | None = None
    fields: list[FormFieldSchema] | None = None

    @model_validator(mode="after")
    def _unique_ids(self) -> FormTemplateUpdate:
        if self.fields is None:
            return self
        ids = [f.id for f in self.fields]
        if len(ids) != len(set(ids)):
            raise ValueError("Идентификаторы полей (id) должны быть уникальны")
        return self


class FormTemplateResponse(BaseModel):
    id: UUID
    name: str
    description: str
    fields: list[FormFieldSchema]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": False}


class RegistrationEventCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    form_template_id: UUID
    event_start_date: date
    event_end_date: date
    registration_deadline_at: datetime | None = None
    schedule_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def _dates(self) -> RegistrationEventCreate:
        if self.event_end_date < self.event_start_date:
            raise ValueError("Дата окончания мероприятия не может быть раньше даты начала")
        return self


class RegistrationEventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    form_template_id: UUID | None = None
    event_start_date: date | None = None
    event_end_date: date | None = None
    registration_deadline_at: datetime | None = None
    registration_closed_early: bool | None = None
    schedule_ids: list[UUID] | None = None

    @model_validator(mode="after")
    def _dates(self) -> RegistrationEventUpdate:
        if self.event_start_date is not None and self.event_end_date is not None:
            if self.event_end_date < self.event_start_date:
                raise ValueError("Дата окончания не может быть раньше даты начала")
        return self


class RegistrationEventListItem(BaseModel):
    id: UUID
    title: str
    form_template_id: UUID
    form_template_name: str
    event_start_date: date
    event_end_date: date
    registration_deadline_at: datetime
    registration_closed_early: bool
    registration_open: bool
    submissions_count: int
    schedule_ids: list[UUID]
    created_at: datetime
    updated_at: datetime


class RegistrationEventDetail(RegistrationEventListItem):
    pass


class RegistrationSubmissionItem(BaseModel):
    id: UUID
    event_id: UUID
    answers: dict[str, Any]
    submitted_at: datetime


class PublicRegistrationPayload(BaseModel):
    """Публичная карточка мероприятия + поля формы (если регистрация открыта)."""

    event_id: UUID
    event_title: str
    event_start_date: date
    event_end_date: date
    registration_open: bool
    closed_message: str = "Регистрация завершена."
    fields: list[FormFieldSchema] = Field(default_factory=list)


class PublicRegistrationSubmitBody(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
