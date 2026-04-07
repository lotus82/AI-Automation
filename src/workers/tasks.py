"""Задачи воркера Celery."""

from __future__ import annotations

import logging

from src.core.celery_app import app

logger = logging.getLogger(__name__)
from src.workers.analyst import analyze_conversation_sync
from src.workers.dialer import run_outbound_campaign_sync
from src.workers.scheduler import run_schedules_sync


@app.task(name="analyze_conversation_task")
def analyze_conversation_task(session_id: str) -> str:
    """Очередь: история Redis → call_records → LLM (ОКК) → call_analytics."""
    return analyze_conversation_sync(session_id)


@app.task(name="run_outbound_campaign_task")
def run_outbound_campaign_task() -> int:
    """Очередь: pending из dialer_queue → ITelephonyService.make_outbound_call (заглушка или SIP)."""
    return run_outbound_campaign_sync()


@app.task(name="check_and_execute_schedules")
def check_and_execute_schedules() -> str:
    """Beat раз в минуту: DATABASE / INTERVAL / REMINDER → LLM + MAX (фаза 18)."""
    return run_schedules_sync()


@app.task(name="process_bitrix24_event")
def process_bitrix24_event_task(portal_id: str, event: str, data: dict) -> str:
    """Фоновая обработка событий Bitrix24 (лиды, сделки); тело — заглушка под бизнес-логику."""
    logger.info(
        "Bitrix24 Celery: event=%s portal_id=%s data_keys=%s",
        event,
        portal_id,
        list(data.keys())[:30] if isinstance(data, dict) else type(data).__name__,
    )
    return "ok"
