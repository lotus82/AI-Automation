"""Чтение и изменение системных настроек из панели (руководитель отдела продаж).

# TODO: В продакшене ограничить доступ (роль, JWT, VPN) — сейчас эндпоинты открыты как остальной API.
"""

from __future__ import annotations

import json
import uuid
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.api.dependencies import AsyncSessionDep, RedisDep
from src.api.dependencies_portal import PortalUserDep
from src.api.schemas.settings import SettingsUpdateRequest, SystemSettingPublic
from src.domain import system_setting_keys as sk
from src.api.org_scope import resolve_organization_scope
from src.core.config import get_settings
from src.domain.entities import SystemSetting
from src.infrastructure.max_bot_identity import sync_max_bot_user_id_for_token
from src.infrastructure.repositories import PostgresSettingsRepository

router = APIRouter(tags=["settings"])


def _mask_setting_value(key: str, value: str) -> str:
    """Маскирует секреты для отображения в UI (например, sk-xx…1234)."""
    if key not in sk.SECRET_VALUE_KEYS:
        return value
    if not value:
        return ""
    if len(value) <= 8:
        return "••••••••"
    return f"{value[:4]}…{value[-4:]}"


def _to_public(row: SystemSetting, *, masked: bool) -> SystemSettingPublic:
    v = _mask_setting_value(row.key, row.value) if masked else row.value
    return SystemSettingPublic(
        key=row.key,
        value=v,
        description=row.description,
        updated_at=row.updated_at,
    )


@router.get("/settings", response_model=list[SystemSettingPublic])
async def list_settings(
    user: PortalUserDep,
    session: AsyncSessionDep,
    redis: RedisDep,
    organization_id: UUID | None = Query(
        None,
        description="Супер-админ: id организации; без параметра — глобальные настройки экземпляра",
    ),
) -> list[SystemSettingPublic]:
    """Все настройки; API-ключи и токены отдаются в маскированном виде."""
    scope = resolve_organization_scope(user, organization_id)
    repo = PostgresSettingsRepository(session, redis, organization_id=scope)
    rows = await repo.list_all()
    return [_to_public(r, masked=True) for r in rows]


@router.put("/settings", status_code=status.HTTP_200_OK)
async def update_settings(
    body: SettingsUpdateRequest,
    user: PortalUserDep,
    session: AsyncSessionDep,
    redis: RedisDep,
    organization_id: UUID | None = Query(
        None,
        description="Супер-админ: id организации; без параметра — глобальные настройки",
    ),
) -> dict[str, bool]:
    """Пакетное обновление. Неизвестные ключи отклоняются."""
    if not body.values:
        return {"ok": True}

    normalized = {k.strip(): v for k, v in body.values.items()}

    for ks in normalized:
        if ks not in sk.UPDATABLE_KEYS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ключ не разрешён к изменению через API: {ks}",
            )

    if sk.LLM_PROVIDER in normalized:
        low = (normalized[sk.LLM_PROVIDER] or "").strip().lower()
        if low not in ("deepseek", "openai"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="LLM_PROVIDER должен быть deepseek или openai",
            )

    if sk.LLM_TEMPERATURE in normalized:
        raw_t = (normalized[sk.LLM_TEMPERATURE] or "").strip().replace(",", ".")
        try:
            temp = float(raw_t)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="LLM_TEMPERATURE должен быть числом (например 0.2)",
            ) from None
        if temp < 0.0 or temp > 1.0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="LLM_TEMPERATURE допустим от 0.0 до 1.0",
            )
        # Шаг 0.1 для предсказуемости в UI
        normalized[sk.LLM_TEMPERATURE] = str(round(temp * 10) / 10)

    if sk.SALUTESPEECH_SCOPE in normalized:
        sc = (normalized[sk.SALUTESPEECH_SCOPE] or "").strip()
        if not sc or len(sc) > 128:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SALUTESPEECH_SCOPE не может быть пустым (максимум 128 символов)",
            )

    if sk.SALUTESPEECH_VOICE in normalized:
        v = (normalized[sk.SALUTESPEECH_VOICE] or "").strip()
        if len(v) > 128:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SALUTESPEECH_VOICE слишком длинный (максимум 128 символов)",
            )

    if sk.MAX_BOT_TOKEN in normalized:
        t = normalized[sk.MAX_BOT_TOKEN] or ""
        if len(t) > 512:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MAX_BOT_TOKEN слишком длинный (максимум 512 символов)",
            )

    if sk.MAX_CONTEXT_LIMIT in normalized:
        raw = (normalized[sk.MAX_CONTEXT_LIMIT] or "").strip()
        try:
            n = int(raw)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MAX_CONTEXT_LIMIT должен быть целым числом",
            ) from None
        if n < 1 or n > 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MAX_CONTEXT_LIMIT допустим от 1 до 200",
            )

    if sk.TEXT_BOT_SYSTEM_SUPPLEMENT in normalized:
        sup = normalized[sk.TEXT_BOT_SYSTEM_SUPPLEMENT] or ""
        if len(sup) > 32000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TEXT_BOT_SYSTEM_SUPPLEMENT слишком длинный (максимум 32000 символов)",
            )

    if sk.MAX_USE_POLLING in normalized:
        v = (normalized[sk.MAX_USE_POLLING] or "").strip().lower()
        if v not in ("0", "1", "true", "false", "yes", "no", "on", "off"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MAX_USE_POLLING: укажите 0/1, true/false, yes/no, on/off",
            )
        normalized[sk.MAX_USE_POLLING] = "1" if v in ("1", "true", "yes", "on") else "0"

    if sk.MAX_VOICE_REPLY_ENABLED in normalized:
        v = (normalized[sk.MAX_VOICE_REPLY_ENABLED] or "").strip().lower()
        if v not in ("0", "1", "true", "false", "yes", "no", "on", "off"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MAX_VOICE_REPLY_ENABLED: укажите 0/1, true/false, yes/no, on/off",
            )
        normalized[sk.MAX_VOICE_REPLY_ENABLED] = "1" if v in ("1", "true", "yes", "on") else "0"

    if sk.MAX_BOT_USERNAME in normalized:
        u = (normalized[sk.MAX_BOT_USERNAME] or "").strip()
        if len(u) > 128:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MAX_BOT_USERNAME слишком длинный (максимум 128 символов)",
            )

    if sk.MAX_GROUP_CHAT_ID in normalized:
        gid = (normalized[sk.MAX_GROUP_CHAT_ID] or "").strip()
        if len(gid) > 64:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MAX_GROUP_CHAT_ID слишком длинный (максимум 64 символа)",
            )

    if sk.MAX_GROUP_ADDITIONAL_PROMPT in normalized:
        gp = normalized[sk.MAX_GROUP_ADDITIONAL_PROMPT] or ""
        if len(gp) > 32000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MAX_GROUP_ADDITIONAL_PROMPT слишком длинный (максимум 32000 символов)",
            )

    if sk.SYSTEM_ROLES_CONFIG in normalized:
        raw_sr = (normalized[sk.SYSTEM_ROLES_CONFIG] or "").strip()
        if not raw_sr:
            normalized[sk.SYSTEM_ROLES_CONFIG] = ""
        else:
            if len(raw_sr) > 524288:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="SYSTEM_ROLES_CONFIG слишком большой (максимум 512 КБ)",
                )
            try:
                sr = json.loads(raw_sr)
            except json.JSONDecodeError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"SYSTEM_ROLES_CONFIG: невалидный JSON ({e})",
                ) from e
            if not isinstance(sr, dict):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="SYSTEM_ROLES_CONFIG должен быть JSON-объектом",
                )
            roles = sr.get("roles")
            if not isinstance(roles, list) or len(roles) < 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="SYSTEM_ROLES_CONFIG: нужен непустой массив roles",
                )
            if len(roles) > 50:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="SYSTEM_ROLES_CONFIG: не более 50 ролей",
                )
            role_ids: set[str] = set()
            norm_roles: list[dict] = []
            for i, r in enumerate(roles):
                if not isinstance(r, dict):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"SYSTEM_ROLES_CONFIG: roles[{i}] должен быть объектом",
                    )
                rid = str(r.get("id", "")).strip()
                if not rid:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"SYSTEM_ROLES_CONFIG: у roles[{i}] нужен непустой id (UUID)",
                    )
                if len(rid) > 64:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"SYSTEM_ROLES_CONFIG: слишком длинный id у roles[{i}]",
                    )
                try:
                    uuid.UUID(rid)
                except ValueError as e:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"SYSTEM_ROLES_CONFIG: id роли должен быть UUID (roles[{i}])",
                    ) from e
                if rid in role_ids:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"SYSTEM_ROLES_CONFIG: дубликат id роли {rid}",
                    )
                role_ids.add(rid)
                name = str(r.get("name", "")).strip()
                if len(name) > 200:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"SYSTEM_ROLES_CONFIG: слишком длинное имя роли (roles[{i}])",
                    )
                pr = r.get("prompt")
                if not isinstance(pr, str):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"SYSTEM_ROLES_CONFIG: prompt должен быть строкой (roles[{i}])",
                    )
                if len(pr) > 32000:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"SYSTEM_ROLES_CONFIG: prompt слишком длинный (roles[{i}])",
                    )
                norm_roles.append({"id": rid, "name": name, "prompt": pr})

            default_rid = str(sr.get("default_role_id", "")).strip()
            if not default_rid or default_rid not in role_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="SYSTEM_ROLES_CONFIG: default_role_id должен совпадать с id одной из ролей",
                )
            analyst_raw = sr.get("analyst_role_id")
            analyst_rid = str(analyst_raw).strip() if analyst_raw is not None and str(analyst_raw).strip() else ""
            if analyst_rid and analyst_rid not in role_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="SYSTEM_ROLES_CONFIG: analyst_role_id должен быть id одной из ролей или пустым",
                )
            out_sr = {
                "default_role_id": default_rid,
                "analyst_role_id": analyst_rid or None,
                "roles": norm_roles,
            }
            normalized[sk.SYSTEM_ROLES_CONFIG] = json.dumps(out_sr, ensure_ascii=False)
            for r in norm_roles:
                if r["id"] == default_rid:
                    normalized[sk.DEFAULT_CONSULTANT_PROMPT] = r["prompt"]
                    break
            if analyst_rid:
                for r in norm_roles:
                    if r["id"] == analyst_rid:
                        normalized[sk.ANALYST_QA_PROMPT] = r["prompt"]
                        break

    if sk.MAX_GROUP_CHAT_PROMPTS in normalized:
        raw_j = (normalized[sk.MAX_GROUP_CHAT_PROMPTS] or "").strip()
        if not raw_j:
            normalized[sk.MAX_GROUP_CHAT_PROMPTS] = "{}"
        else:
            if len(raw_j) > 524288:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="MAX_GROUP_CHAT_PROMPTS слишком большой (максимум 512 КБ)",
                )
            try:
                parsed = json.loads(raw_j)
            except json.JSONDecodeError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"MAX_GROUP_CHAT_PROMPTS: невалидный JSON ({e})",
                ) from e
            if not isinstance(parsed, dict):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="MAX_GROUP_CHAT_PROMPTS должен быть JSON-объектом chat_id → настройки группы",
                )
            if len(parsed) > 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="MAX_GROUP_CHAT_PROMPTS: не более 200 групповых чатов",
                )
            out: dict[str, dict[str, str | None]] = {}
            for k_raw, v_raw in parsed.items():
                ks = str(k_raw).strip() if k_raw is not None else ""
                if not ks:
                    continue
                if len(ks) > 64:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"MAX_GROUP_CHAT_PROMPTS: слишком длинный chat_id (макс. 64): {ks[:20]}…",
                    )
                role_id: str | None = None
                add = ""
                desc: str | None = None
                if isinstance(v_raw, str):
                    add = v_raw.strip()
                elif isinstance(v_raw, dict):
                    rr = v_raw.get("role_id")
                    if rr is not None and str(rr).strip():
                        cand = str(rr).strip()
                        if len(cand) > 64:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"MAX_GROUP_CHAT_PROMPTS: слишком длинный role_id для {ks[:16]}",
                            )
                        try:
                            uuid.UUID(cand)
                        except ValueError as e:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"MAX_GROUP_CHAT_PROMPTS: role_id для {ks[:16]} должен быть UUID",
                            ) from e
                        role_id = cand
                    ap = v_raw.get("additional_prompt")
                    add = ap.strip() if isinstance(ap, str) else ""
                    if "description" in v_raw:
                        dp = v_raw.get("description")
                        dstr = dp.strip() if isinstance(dp, str) else ""
                        if len(dstr) > 4000:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"MAX_GROUP_CHAT_PROMPTS: description для {ks[:16]}… слишком длинный",
                            )
                        desc = dstr or None
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"MAX_GROUP_CHAT_PROMPTS: для chat_id {ks[:16]}… значение — строка или объект",
                    )
                if len(add) > 32000:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"MAX_GROUP_CHAT_PROMPTS: additional_prompt для {ks[:16]}… слишком длинный",
                    )
                piece: dict[str, str | None] = {"role_id": role_id, "additional_prompt": add}
                if desc:
                    piece["description"] = desc
                out[ks] = piece
            normalized[sk.MAX_GROUP_CHAT_PROMPTS] = json.dumps(out, ensure_ascii=False)

    if sk.MAX_CALL_ANSWER_DELAY in normalized:
        raw_d = (normalized[sk.MAX_CALL_ANSWER_DELAY] or "").strip()
        try:
            d = int(raw_d)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MAX_CALL_ANSWER_DELAY должен быть целым числом (секунды)",
            ) from None
        if d < 0 or d > 120:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MAX_CALL_ANSWER_DELAY допустим от 0 до 120 секунд",
            )
        normalized[sk.MAX_CALL_ANSWER_DELAY] = str(d)

    if sk.MAX_CALL_GREETING_PHRASE in normalized:
        gr = normalized[sk.MAX_CALL_GREETING_PHRASE] or ""
        if len(gr) > 4000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MAX_CALL_GREETING_PHRASE слишком длинный (максимум 4000 символов)",
            )

    scope = resolve_organization_scope(user, organization_id)
    repo = PostgresSettingsRepository(session, redis, organization_id=scope)
    try:
        await repo.upsert_values(normalized)
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    if sk.MAX_BOT_TOKEN in normalized:
        tok = (normalized[sk.MAX_BOT_TOKEN] or "").strip()
        if tok:
            await sync_max_bot_user_id_for_token(
                session,
                redis,
                organization_id=scope,
                token=tok,
                platform_api_base=get_settings().max_platform_api_base,
            )

    return {"ok": True}
