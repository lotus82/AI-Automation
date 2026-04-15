"""Системные роли (SYSTEM_ROLES_CONFIG) и промпты для чата / групп MAX / ОКК."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from src.domain import system_setting_keys as sk
from src.domain.default_system_prompts import (
    FALLBACK_ANALYST_QA_PROMPT,
    FALLBACK_DEFAULT_CONSULTANT_PROMPT,
)

logger = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.I,
)


def parse_roles_config_raw(raw: str) -> dict[str, Any] | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    roles = data.get("roles")
    if not isinstance(roles, list) or len(roles) == 0:
        return None
    return data


def normalize_max_group_map_value(v: Any) -> tuple[str | None, str]:
    """(role_id | None, additional_prompt). Устаревший формат: строка → (None, текст)."""
    if isinstance(v, str):
        return (None, v.strip())
    if isinstance(v, dict):
        rid_raw = v.get("role_id")
        rid_s: str | None = None
        if rid_raw is not None and str(rid_raw).strip():
            cand = str(rid_raw).strip()
            rid_s = cand if _UUID_RE.match(cand) else None
        ap = v.get("additional_prompt")
        add = ap.strip() if isinstance(ap, str) else ""
        return (rid_s, add)
    return (None, "")


def _prompt_for_role_id(cfg: dict[str, Any], role_id: str | None) -> str | None:
    if not role_id:
        return None
    roles = cfg.get("roles")
    if not isinstance(roles, list):
        return None
    for r in roles:
        if not isinstance(r, dict):
            continue
        if str(r.get("id", "")).strip() == role_id:
            p = r.get("prompt")
            return p.strip() if isinstance(p, str) else None
    return None


async def get_effective_consultant_prompt(repo: Any, *, session_id: str) -> str:
    """Системный промпт консультанта: роль из настройки группы MAX или основная роль по умолчанию."""
    sid = (session_id or "").strip()
    group_role_id: str | None = None
    raw_map = (await repo.get_value(sk.MAX_GROUP_CHAT_PROMPTS) or "").strip()
    if raw_map and sid:
        try:
            data = json.loads(raw_map)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict) and sid in data:
            group_role_id, _ = normalize_max_group_map_value(data[sid])

    cfg_raw = (await repo.get_value(sk.SYSTEM_ROLES_CONFIG) or "").strip()
    cfg = parse_roles_config_raw(cfg_raw)

    chosen_id: str | None = group_role_id
    if cfg:
        default_rid = str(cfg.get("default_role_id") or "").strip()
        if not chosen_id:
            chosen_id = default_rid or None
        prompt = _prompt_for_role_id(cfg, chosen_id)
        if prompt:
            return prompt

    legacy = (await repo.get_value(sk.DEFAULT_CONSULTANT_PROMPT) or "").strip()
    return legacy or FALLBACK_DEFAULT_CONSULTANT_PROMPT


async def get_default_consultant_prompt(repo: Any) -> str:
    """Промпт основной роли (расписание, ответы без привязки к группе MAX)."""
    cfg_raw = (await repo.get_value(sk.SYSTEM_ROLES_CONFIG) or "").strip()
    cfg = parse_roles_config_raw(cfg_raw)
    if cfg:
        dr = str(cfg.get("default_role_id") or "").strip()
        p = _prompt_for_role_id(cfg, dr)
        if p:
            return p
    legacy = (await repo.get_value(sk.DEFAULT_CONSULTANT_PROMPT) or "").strip()
    return legacy or FALLBACK_DEFAULT_CONSULTANT_PROMPT


async def get_analyst_prompt(repo: Any) -> str:
    """Промпт сценария ОКК / анализа качества."""
    cfg_raw = (await repo.get_value(sk.SYSTEM_ROLES_CONFIG) or "").strip()
    cfg = parse_roles_config_raw(cfg_raw)
    if cfg:
        ar = cfg.get("analyst_role_id")
        ars = str(ar).strip() if ar is not None and str(ar).strip() else ""
        if ars:
            p = _prompt_for_role_id(cfg, ars)
            if p:
                return p
    legacy = (await repo.get_value(sk.ANALYST_QA_PROMPT) or "").strip()
    return legacy or FALLBACK_ANALYST_QA_PROMPT


async def get_max_group_additional_prompt(repo: Any, session_id: str) -> str:
    """Только дополнительный фрагмент для группового чата (после базового промпта и CRM)."""
    sid = (session_id or "").strip()
    raw_map = (await repo.get_value(sk.MAX_GROUP_CHAT_PROMPTS) or "").strip()
    extra = ""
    matched = False
    if raw_map:
        try:
            data = json.loads(raw_map)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict) and sid in data:
            matched = True
            _, extra = normalize_max_group_map_value(data[sid])
    if not matched:
        configured = (await repo.get_value(sk.MAX_GROUP_CHAT_ID) or "").strip()
        if configured and sid == configured:
            extra = (await repo.get_value(sk.MAX_GROUP_ADDITIONAL_PROMPT) or "").strip()
    return (extra or "").strip()
