"""Проверка строки initData мини-приложения MAX (см. https://dev.max.ru/docs/webapps/validation)."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import unquote


def _parse_init_data_key_values(raw: str) -> list[tuple[str, str]] | None:
    """Разбор ``key=value&...`` с одним вхождением каждого ключа (кроме контроля ``hash``)."""
    raw = (raw or "").strip()
    if not raw:
        return None
    pairs: list[tuple[str, str]] = []
    for part in raw.split("&"):
        if not part:
            continue
        if "=" not in part:
            return None
        k, v = part.split("=", 1)
        if not k:
            return None
        pairs.append((k, unquote(v)))
    return pairs


def validate_max_webapp_init_data(
    raw_init_data: str,
    bot_token: str,
    *,
    max_age_sec: int = 3600,
) -> dict[str, str] | None:
    """Проверяет подпись и срок ``auth_date``. При успехе возвращает словарь полей (в т.ч. ``user``, ``start_param``)."""
    bot_token = (bot_token or "").strip()
    pairs = _parse_init_data_key_values(raw_init_data)
    if not pairs or not bot_token:
        return None

    hash_vals = [v for k, v in pairs if k == "hash"]
    if len(hash_vals) != 1:
        return None
    received_hash = hash_vals[0]

    keys_seen: set[str] = set()
    for k, _ in pairs:
        if k == "hash":
            continue
        if k in keys_seen:
            return None
        keys_seen.add(k)

    auth_date_raw = next((v for k, v in pairs if k == "auth_date"), None)
    if auth_date_raw is None:
        return None
    try:
        auth_ts = int(auth_date_raw)
    except ValueError:
        return None
    if int(time.time()) - auth_ts > max_age_sec:
        return None

    non_hash = [(k, v) for k, v in pairs if k != "hash"]
    non_hash.sort(key=lambda kv: kv[0])
    launch_params = "\n".join(f"{k}={v}" for k, v in non_hash)

    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    signature = hmac.new(
        key=secret_key,
        msg=launch_params.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, received_hash):
        return None

    return {k: v for k, v in pairs}


def max_init_data_max_user_id(fields: dict[str, str]) -> str | None:
    """Извлекает числовой id пользователя MAX из поля ``user`` (JSON)."""
    raw = fields.get("user")
    if not raw:
        return None
    try:
        obj: Any = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    uid = obj.get("id")
    if uid is None:
        return None
    return str(uid).strip() or None


def max_init_data_start_param(fields: dict[str, str]) -> str | None:
    v = (fields.get("start_param") or "").strip()
    return v or None
