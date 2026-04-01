"""Схемы ответа для проверки работоспособности."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Тело ответа эндпоинта проверки здоровья сервиса."""

    status: str = Field(default="ok", description="Статус API")
