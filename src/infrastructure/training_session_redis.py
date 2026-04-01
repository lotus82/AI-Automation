"""Метаданные тренировочной сессии в Redis (связь chat session_id → сценарий для воркера ОКК/тренера)."""

from __future__ import annotations

import json
from typing import Any

# Префикс ключа: воркер читает и снимает флаг после анализа.
_TRAINER_KEY_PREFIX = "trainer_session:"


def trainer_session_redis_key(session_id: str) -> str:
    """Ключ Redis для пометки сессии как тренировочной."""
    return f"{_TRAINER_KEY_PREFIX}{session_id.strip()}"


def encode_trainer_meta(*, scenario_id: str, manager_name: str) -> str:
    """JSON для SET (decode_responses=True → строка)."""
    payload: dict[str, Any] = {
        "scenario_id": scenario_id.strip(),
        "manager_name": (manager_name or "").strip(),
    }
    return json.dumps(payload, ensure_ascii=False)


def decode_trainer_meta(raw: str | None) -> tuple[str, str] | None:
    """Возвращает (scenario_id, manager_name) или None при ошибке/пустоте."""
    if not raw or not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    sid = str(data.get("scenario_id", "")).strip()
    if not sid:
        return None
    name = str(data.get("manager_name", "")).strip()
    return sid, name
