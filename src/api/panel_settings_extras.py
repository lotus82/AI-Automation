"""Валидация, маскирование и merge секретов для ``PANEL_SETTINGS_EXTRAS`` (таблицы в настройках)."""

from __future__ import annotations

import json
from typing import Any

KIND_NOTE = "note"
KIND_TBANK_VK_STT = "tbank_voicekit_stt"
KIND_TBANK_VK_TTS = "tbank_voicekit_tts"
_ALLOWED_KINDS = frozenset({KIND_NOTE, KIND_TBANK_VK_STT, KIND_TBANK_VK_TTS})


def _mask_one_secret(s: str) -> str:
    t = (s or "").strip()
    if not t:
        return ""
    if len(t) <= 8:
        return "••••••••"
    return f"{t[:4]}…{t[-4:]}"


def _looks_like_masked(s: str) -> bool:
    return "…" in s and 6 <= len(s) <= 128


def mask_panel_extras_json(value: str) -> str:
    """Маскирует ``config.api_key`` / ``config.secret_key`` в JSON (для GET /api/settings)."""
    if not value or not str(value).strip():
        return value
    try:
        data: Any = json.loads(value)
    except json.JSONDecodeError:
        return value
    if not isinstance(data, dict):
        return value
    for tab in ("llm", "stt", "tts"):
        arr = data.get(tab)
        if not isinstance(arr, list):
            continue
        for it in arr:
            if not isinstance(it, dict):
                continue
            if (it.get("kind") or KIND_NOTE) not in (KIND_TBANK_VK_STT, KIND_TBANK_VK_TTS):
                continue
            conf = it.get("config")
            if not isinstance(conf, dict):
                continue
            for k in ("api_key", "secret_key"):
                v = conf.get(k)
                if not isinstance(v, str) or not v.strip():
                    conf[k] = ""
                    continue
                if _looks_like_masked(v):
                    continue
                if len(v) > 4:
                    conf[k] = _mask_one_secret(v)
    try:
        return json.dumps(data, ensure_ascii=False)
    except (TypeError, ValueError):
        return value


def _kind_valid_for_tab(tab: str, kind: str) -> bool:
    if tab == "llm":
        return kind == KIND_NOTE
    if tab == "stt":
        return kind in (KIND_NOTE, KIND_TBANK_VK_STT)
    if tab == "tts":
        return kind in (KIND_NOTE, KIND_TBANK_VK_TTS)
    return False


def _validate_and_build_extras(blueprint: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(blueprint, dict):
        raise ValueError("PANEL_SETTINGS_EXTRAS: ожидается JSON-объект")
    out: dict[str, list[dict[str, Any]]] = {"llm": [], "stt": [], "tts": []}
    for tab in ("llm", "stt", "tts"):
        arr = blueprint.get(tab, [])
        if not isinstance(arr, list):
            raise ValueError(f"PANEL_SETTINGS_EXTRAS: {tab} должен быть массивом")
        if len(arr) > 100:
            raise ValueError(f"PANEL_SETTINGS_EXTRAS: в {tab} не более 100 записей")
        for i, it in enumerate(arr):
            if not isinstance(it, dict):
                raise ValueError(f"PANEL_SETTINGS_EXTRAS: {tab}[{i}] — объект")
            iid = str(it.get("id", "")).strip()
            if not iid or len(iid) > 64:
                raise ValueError(f"PANEL_SETTINGS_EXTRAS: {tab}[{i}] — id 1…64")
            name = str(it.get("name", "")).strip()
            if not name or len(name) > 200:
                raise ValueError(f"PANEL_SETTINGS_EXTRAS: {tab}[{i}] — name 1…200")
            kind = str(it.get("kind") or KIND_NOTE).strip() or KIND_NOTE
            if kind not in _ALLOWED_KINDS:
                raise ValueError(
                    f"PANEL_SETTINGS_EXTRAS: {tab}[{i}] — неизвестный kind: {kind}"
                )
            if not _kind_valid_for_tab(tab, kind):
                raise ValueError(
                    f"PANEL_SETTINGS_EXTRAS: kind «{kind}» недопустим для вкладки {tab}"
                )
            val = it.get("value", "")
            if not isinstance(val, str):
                raise ValueError(
                    f"PANEL_SETTINGS_EXTRAS: {tab}[{i}] — value должен быть строкой"
                )
            if kind == KIND_NOTE:
                if len(val) > 8000:
                    raise ValueError(
                        f"PANEL_SETTINGS_EXTRAS: {tab}[{i}] — value макс. 8000 символов"
                    )
                out[tab].append(
                    {
                        "id": iid,
                        "name": name,
                        "kind": KIND_NOTE,
                        "value": val,
                    }
                )
            else:
                cfg = it.get("config")
                if not isinstance(cfg, dict):
                    raise ValueError(
                        f"PANEL_SETTINGS_EXTRAS: {tab}[{i}] — для T-Bank VoiceKit нужен config"
                    )
                api_key = str(cfg.get("api_key") or "").strip()
                sec_key = str(cfg.get("secret_key") or "").strip()
                endpoint = str(cfg.get("endpoint") or "").strip()
                for label, s, mlen in (
                    ("api_key", api_key, 512),
                    ("secret_key", sec_key, 512),
                    ("endpoint", endpoint, 256),
                ):
                    if len(s) > mlen:
                        raise ValueError(
                            f"PANEL_SETTINGS_EXTRAS: {tab}[{i}] config.{label} слишком длинно (макс. {mlen})"
                        )
                out[tab].append(
                    {
                        "id": iid,
                        "name": name,
                        "kind": kind,
                        "value": "",
                        "config": {
                            "api_key": api_key,
                            "secret_key": sec_key,
                            "endpoint": endpoint,
                        },
                    }
                )
    return out


def merge_panel_extras_preserve_vk_secrets(
    new_ex: dict[str, list[dict[str, Any]]],
    old_ex: Any,
) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(old_ex, dict):
        return new_ex
    old_index: dict[str, dict[str, Any]] = {}
    for tab in ("llm", "stt", "tts"):
        arr = old_ex.get(tab)
        if not isinstance(arr, list):
            continue
        for it in arr:
            if isinstance(it, dict) and it.get("id") is not None:
                key = f"{tab}:{it['id']}"
                old_index[key] = it

    merged: dict[str, list[dict[str, Any]]] = {"llm": [], "stt": [], "tts": []}
    for tab in ("llm", "stt", "tts"):
        for it in new_ex[tab]:
            kind = it.get("kind") or KIND_NOTE
            oid = it.get("id")
            oi = old_index.get(f"{tab}:{oid}") if oid else None
            if (
                oi
                and kind in (KIND_TBANK_VK_STT, KIND_TBANK_VK_TTS)
                and oi.get("kind") == kind
            ):
                ncfg = it.get("config")
                ocfg = oi.get("config") if isinstance(oi.get("config"), dict) else {}
                if isinstance(ncfg, dict):
                    for nk in ("api_key", "secret_key"):
                        nval = str(ncfg.get(nk) or "").strip()
                        oval = str(ocfg.get(nk) or "").strip() if ocfg else ""
                        if (not nval) or _looks_like_masked(nval) or nval == "••••••••":
                            if oval:
                                ncfg[nk] = oval
            merged[tab].append(it)
    return merged


def _ensure_vk_keys_present(ex: dict[str, list[dict[str, Any]]]) -> None:
    for tab, label in (("stt", "STT"), ("tts", "TTS")):
        for it in ex[tab]:
            if it.get("kind") not in (KIND_TBANK_VK_STT, KIND_TBANK_VK_TTS):
                continue
            cfg = it.get("config")
            if not isinstance(cfg, dict):
                raise ValueError(
                    f"PANEL_SETTINGS_EXTRAS: T-Bank VoiceKit ({label}) «{it.get('name', '?')}»: нет config"
                )
            a = str(cfg.get("api_key") or "").strip()
            s = str(cfg.get("secret_key") or "").strip()
            if not a or not s or _looks_like_masked(a) or _looks_like_masked(s):
                raise ValueError(
                    f"PANEL_SETTINGS_EXTRAS: T-Bank VoiceKit ({label}) «{it.get('name', '?')}»: "
                    "нужны и API key, и secret key (нельзя сохранить только маску с экрана — "
                    "введите ключи при первом добавлении или оставьте неизменным после сохранения в БД)."
                )


def process_panel_extras_incoming(
    raw_ex: str,
    *,
    old_raw: str | None,
) -> str:
    try:
        ex = json.loads(raw_ex)
    except json.JSONDecodeError as e:
        raise ValueError(f"PANEL_SETTINGS_EXTRAS: невалидный JSON ({e})") from e
    built = _validate_and_build_extras(ex)
    old = None
    if old_raw and str(old_raw).strip():
        try:
            old = json.loads(old_raw)
        except json.JSONDecodeError:
            old = None
    merged = merge_panel_extras_preserve_vk_secrets(built, old)
    _ensure_vk_keys_present(merged)
    return json.dumps(merged, ensure_ascii=False)
