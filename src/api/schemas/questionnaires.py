"""Схемы API опросников."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

QuestionType = Literal["single", "multiple", "text"]


class QuestionOptionCreate(BaseModel):
    text: str = Field(..., min_length=1)
    score: float = 0.0


class QuestionCreate(BaseModel):
    text: str = Field(..., min_length=1)
    type: QuestionType
    order: int = Field(default=0, ge=0)
    min_score: float = Field(default=0.0)
    max_score: float = Field(default=10.0)
    options: list[QuestionOptionCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_options_and_scores(self) -> QuestionCreate:
        if self.max_score < self.min_score:
            raise ValueError("max_score должен быть >= min_score")
        if self.type in ("single", "multiple"):
            if not self.options:
                raise ValueError("Для типов single и multiple нужен хотя бы один вариант ответа")
            for o in self.options:
                if not (self.min_score <= o.score <= self.max_score):
                    raise ValueError(
                        f"Балл варианта «{o.text[:48]}» ({o.score}) вне диапазона "
                        f"[{self.min_score}, {self.max_score}]"
                    )
        elif self.options:
            raise ValueError("У текстового вопроса не должно быть вариантов ответа")
        return self


class QuestionnaireCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    llm_criteria: str = ""
    questions: list[QuestionCreate] = Field(default_factory=list)


class QuestionnaireUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    llm_criteria: str = ""
    questions: list[QuestionCreate] = Field(default_factory=list)


class QuestionOptionPublic(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    text: str
    score: float


class QuestionPublic(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    text: str
    type: str
    order: int
    min_score: float
    max_score: float
    options: list[QuestionOptionPublic]


class QuestionnairePublic(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    title: str
    llm_criteria: str
    created_at: datetime
    updated_at: datetime
    questions: list[QuestionPublic]


class QuestionnaireListItem(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class AssessAnswerItem(BaseModel):
    question_id: UUID
    option_ids: list[UUID] = Field(default_factory=list)
    text_answer: str | None = None


class AssessRequest(BaseModel):
    answers: list[AssessAnswerItem]


class AssessResponse(BaseModel):
    analysis: str
