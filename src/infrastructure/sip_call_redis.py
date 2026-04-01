"""Ключи Redis для связки SIP call_id ↔ session_id и метаданных записи ОКК."""

from __future__ import annotations

import json
from typing import Any

_ANALYST_META_PREFIX = "analyst_call_meta:"
_SIP_CALL_PREFIX = "sip_call:"


def analyst_call_meta_redis_key(session_id: str) -> str:
    """Метаданные для строки CallRecord (направление, номер) до прохода воркера ОКК."""
    return f"{_ANALYST_META_PREFIX}{session_id.strip()}"


def sip_call_map_redis_key(call_id: str) -> str:
    """Соответствие идентификатора АТС и session_id диалога."""
    return f"{_SIP_CALL_PREFIX}{call_id.strip()}"


def encode_analyst_call_meta(*, direction: str, remote_phone: str) -> str:
    payload: dict[str, Any] = {
        "direction": (direction or "web").strip(),
        "remote_phone": (remote_phone or "").strip()[:64],
    }
    return json.dumps(payload, ensure_ascii=False)


def decode_analyst_call_meta(raw: str | None) -> tuple[str, str]:
    """Возвращает (direction, remote_phone); при ошибке — ('web', '')."""
    if not raw or not raw.strip():
        return "web", ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return "web", ""
    if not isinstance(data, dict):
        return "web", ""
    d = str(data.get("direction", "web")).strip() or "web"
    p = str(data.get("remote_phone", "")).strip()[:64]
    return d, p


def encode_sip_call_map(*, session_id: str) -> str:
    return json.dumps({"session_id": session_id.strip()}, ensure_ascii=False)


def decode_sip_call_map_session_id(raw: str | None) -> str | None:
    if not raw or not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    sid = str(data.get("session_id", "")).strip()
    return sid or None
