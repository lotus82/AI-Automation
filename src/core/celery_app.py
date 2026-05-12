"""Приложение Celery: брокер и результат в Redis (отдельные индексы БД от чата)."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

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
    enable_utc=True,
    beat_schedule={
        "check_and_execute_schedules": {
            "task": "check_and_execute_schedules",
            "schedule": crontab(minute="*"),
        },
        "generate_compliance_deadlines": {
            "task": "generate_compliance_deadlines",
            "schedule": crontab(hour=2, minute=0),
        },
        "notify_upcoming_deadlines": {
            "task": "notify_upcoming_deadlines",
            "schedule": crontab(hour=8, minute=30),
        },
    },
)
# Расписание Beat в локальном часовом поясе приложения (например Europe/Saratov)
app.conf.timezone = _settings.app_timezone

# Регистрация задач после создания `app`, чтобы избежать циклического импорта
import src.workers.tasks  # noqa: E402, F401
