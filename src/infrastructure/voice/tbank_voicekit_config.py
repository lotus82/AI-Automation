"""Загрузка endpoint и ключей T-Bank VoiceKit: .env, затем system_settings (панель + PANEL_SETTINGS_EXTRAS)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from src.api.panel_settings_extras import KIND_TBANK_VK_STT, KIND_TBANK_VK_TTS
from src.core.config import Settings
from src.domain import system_setting_keys as sk
from src.infrastructure.database import AsyncSessionLocal
from src.infrastructure.repositories import PostgresSettingsRepository


@dataclass(frozen=True, slots=True)
class TbankVoiceKitCredentials:
    """Креды для одного контура STT или TTS."""

    api_key: str
    secret_key: str
    """Как в консоли T-Bank: base64, подпись JWT (см. voicekit-examples)."""
    grpc_target: str
    """``host:port`` для gRPC, по умолчанию ``api.tinkoff.ai:443``."""


def normalize_tbank_grpc_target(endpoint: str | None) -> str:
    """Приводит значение из панели/окружения к ``host:port``."""
    raw = (endpoint or "").strip()
    if not raw:
        return "api.tinkoff.ai:443"
    if raw.startswith("https://"):
        rest = raw[8:].split("/")[0].strip()
    elif raw.startswith("http://"):
        rest = raw[7:].split("/")[0].strip()
    else:
        rest = raw
    if ":" in rest:
        return rest
    return f"{rest}:443"


def _extras_panel_obj(raw: str | None) -> dict[str, Any] | None:
    if not raw or not str(raw).strip():
        return None
    try:
        o = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return o if isinstance(o, dict) else None


def _pick_vk_row(
    tab: str,
    extras: dict[str, Any],
    *,
    want_kind: str,
    profile_id: str | None,
) -> dict[str, Any] | None:
    arr = extras.get(tab)
    if not isinstance(arr, list):
        return None
    if profile_id:
        for it in arr:
            if not isinstance(it, dict):
                continue
            if str(it.get("id", "")).strip() == profile_id and str(it.get("kind", "")).strip() == want_kind:
                return it
    for it in arr:
        if not isinstance(it, dict):
            continue
        if str(it.get("kind", "")).strip() == want_kind:
            return it
    return None


def _row_to_creds(row: dict[str, Any] | None) -> TbankVoiceKitCredentials | None:
    if not row:
        return None
    cfg = row.get("config")
    if not isinstance(cfg, dict):
        return None
    api_key = str(cfg.get("api_key") or "").strip()
    sec = str(cfg.get("secret_key") or "").strip()
    ep = str(cfg.get("endpoint") or "").strip()
    if not api_key or not sec:
        return None
    return TbankVoiceKitCredentials(
        api_key=api_key,
        secret_key=sec,
        grpc_target=normalize_tbank_grpc_target(ep or None),
    )


def _creds_from_env(settings: Settings) -> TbankVoiceKitCredentials | None:
    a = (settings.tbank_voicekit_api_key or "").strip()
    s = (settings.tbank_voicekit_secret_key or "").strip()
    if not a or not s:
        return None
    return TbankVoiceKitCredentials(
        api_key=a,
        secret_key=s,
        grpc_target=normalize_tbank_grpc_target(getattr(settings, "tbank_voicekit_endpoint", None)),
    )


async def load_tbank_voicekit_stt_credentials(
    settings: Settings,
    redis: Redis,
    *,
    organization_id: UUID | None = None,
) -> TbankVoiceKitCredentials | None:
    env = _creds_from_env(settings)
    if env is not None:
        return env
    async with AsyncSessionLocal() as session:
        try:
            repo = PostgresSettingsRepository(session, redis, organization_id=organization_id)
            pid = (await repo.get_value(sk.VOICE_TBANK_STT_EXTRAS_ID) or "").strip() or None
            raw_ex = await repo.get_value(sk.PANEL_SETTINGS_EXTRAS)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    ex = _extras_panel_obj(raw_ex)
    if ex is None:
        return None
    row = _pick_vk_row("stt", ex, want_kind=KIND_TBANK_VK_STT, profile_id=pid)
    return _row_to_creds(row)


async def load_tbank_voicekit_tts_credentials(
    settings: Settings,
    redis: Redis,
    *,
    organization_id: UUID | None = None,
) -> TbankVoiceKitCredentials | None:
    env = _creds_from_env(settings)
    if env is not None:
        return env
    async with AsyncSessionLocal() as session:
        try:
            repo = PostgresSettingsRepository(session, redis, organization_id=organization_id)
            pid = (await repo.get_value(sk.VOICE_TBANK_TTS_EXTRAS_ID) or "").strip() or None
            raw_ex = await repo.get_value(sk.PANEL_SETTINGS_EXTRAS)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    ex = _extras_panel_obj(raw_ex)
    if ex is None:
        return None
    row = _pick_vk_row("tts", ex, want_kind=KIND_TBANK_VK_TTS, profile_id=pid)
    return _row_to_creds(row)
