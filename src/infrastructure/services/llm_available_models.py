"""Список идентификаторов моделей для селектора в панели (провайдеры OpenAI-совместимого API)."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

_DEEPSEEK_BASE = "https://api.deepseek.com"
_OPENAI_BASE = "https://api.openai.com"

logger = logging.getLogger(__name__)

# Актуальные идентификаторы чат-моделей по документации DeepSeek (см. Quick Start + Models & Pricing);
# эндпоинт ``GET /v1/models`` нередко отдаёт только устаревшее имя — дополняем ответ вручную.
# https://api-docs.deepseek.com/
_DEEPSEEK_KNOWN_CHAT_MODELS: tuple[str, ...] = (
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "deepseek-chat",
    "deepseek-reasoner",
)

# Если GET не удался вовсе — тот же порядок (v4 → legacy)
_FALLBACK_DEEPSEEK: tuple[str, ...] = _DEEPSEEK_KNOWN_CHAT_MODELS

_FALLBACK_OPENAI: tuple[str, ...] = (
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
    "o1",
    "o1-mini",
    "o1-preview",
    "o3-mini",
)


def _parse_models_payload(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return []
    items = data.get("data")
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for it in items:
        if isinstance(it, dict) and it.get("id"):
            out.append(str(it["id"]).strip())
    return out


def _merge_deepseek_with_documented_ids(from_api: list[str]) -> list[str]:
    """API может вернуть один ``deepseek-chat``; в список для UI добавляем все id из доков DeepSeek
    и лишние id с API, если появятся в будущем."""
    known_lower = {m.lower() for m in _DEEPSEEK_KNOWN_CHAT_MODELS}
    out: list[str] = list(_DEEPSEEK_KNOWN_CHAT_MODELS)
    for m in from_api:
        t = str(m).strip()
        if not t:
            continue
        if t.lower() in known_lower:
            continue
        out.append(t)
    return out


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    api_key: str,
) -> dict[str, Any] | None:
    try:
        r = await client.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
        )
    except httpx.HTTPError as exc:
        logger.warning("LLM list models: запрос %s: %s", url, exc)
        return None
    if r.status_code != 200:
        logger.warning("LLM list models: %s -> HTTP %s", url, r.status_code)
        return None
    try:
        j = r.json()
    except ValueError:
        return None
    return j if isinstance(j, dict) else None


def _filter_openai_chat_models(ids: list[str]) -> list[str]:
    """Убирает очевидно не-чатовые модели из длинного списка OpenAI."""
    out: list[str] = []
    for mid in ids:
        m = mid.lower()
        if any(
            x in m
            for x in (
                "embedding",
                "whisper",
                "davinci",
                "babbage",
                "dall",
                "tts",
                "transcribe",
                "moderation",
            )
        ):
            continue
        if m.startswith("ft:") and "gpt" not in m:
            continue
        if re.match(r"^(gpt-|o[0-9]|chatgpt-)", m):
            out.append(mid)
            continue
        if m in ("o1", "o1-mini", "o1-preview", "o3", "o3-mini"):
            out.append(mid)
    if not out:
        return sorted(set(ids), key=str.lower)[:100]
    return sorted(set(out), key=str.lower)


async def fetch_llm_model_ids(
    *,
    provider: str,
    api_key: str,
    timeout: float = 20.0,
) -> tuple[list[str], str]:
    """Возвращает ``(ids, "api" | "fallback")``."""
    p = (provider or "deepseek").strip().lower()
    key = (api_key or "").strip()
    if p not in ("deepseek", "openai") or not key:
        if p == "openai":
            return list(_FALLBACK_OPENAI), "fallback"
        return list(_FALLBACK_DEEPSEEK), "fallback"

    to = httpx.Timeout(timeout, connect=10.0)
    async with httpx.AsyncClient(timeout=to, trust_env=False) as client:
        if p == "deepseek":
            for path in ("/v1/models", "/models"):
                j = await _get_json(client, f"{_DEEPSEEK_BASE}{path}", api_key=key)
                if not j:
                    continue
                ids = _parse_models_payload(j)
                merged = _merge_deepseek_with_documented_ids(ids)
                if ids and len(merged) > len({str(m).strip().lower() for m in ids if m}):
                    logger.debug(
                        "LLM list models: DeepSeek %s: в ответе %s id(ов), после доп. по доке — %s",
                        path,
                        len(ids),
                        len(merged),
                    )
                return merged, "api"
            return list(_FALLBACK_DEEPSEEK), "fallback"

        j = await _get_json(client, f"{_OPENAI_BASE}/v1/models", api_key=key)
        if not j:
            return list(_FALLBACK_OPENAI), "fallback"
        raw = _parse_models_payload(j)
        if not raw:
            return list(_FALLBACK_OPENAI), "fallback"
        filtered = _filter_openai_chat_models(raw)
        return filtered, "api"
