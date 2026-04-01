"""Задачи воркера Celery."""

from __future__ import annotations

from src.core.celery_app import app
from src.workers.analyst import analyze_conversation_sync
from src.workers.dialer import run_outbound_campaign_sync


@app.task(name="analyze_conversation_task")
def analyze_conversation_task(session_id: str) -> str:
    """Очередь: история Redis → call_records → LLM (ОКК) → call_analytics."""
    return analyze_conversation_sync(session_id)


@app.task(name="run_outbound_campaign_task")
def run_outbound_campaign_task() -> int:
    """Очередь: pending из dialer_queue → ITelephonyService.make_outbound_call (заглушка или SIP)."""
    return run_outbound_campaign_sync()
