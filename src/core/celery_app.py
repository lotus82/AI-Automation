"""Приложение Celery: брокер и результат в Redis (отдельные индексы БД от чата)."""

from __future__ import annotations

from celery import Celery

from src.core.config import get_settings

_settings = get_settings()

app = Celery(
    "sales_agent",
    broker=_settings.celery_broker_url,
    backend=_settings.celery_result_backend,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Регистрация задач после создания `app`, чтобы избежать циклического импорта
import src.workers.tasks  # noqa: E402, F401
