"""Чтение и изменение системных настроек из панели (руководитель отдела продаж).

# TODO: В продакшене ограничить доступ (роль, JWT, VPN) — сейчас эндпоинты открыты как остальной API.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from src.api.dependencies import SettingsRepositoryDep
from src.api.schemas.settings import SettingsUpdateRequest, SystemSettingPublic
from src.domain import system_setting_keys as sk
from src.domain.entities import SystemSetting

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
async def list_settings(repo: SettingsRepositoryDep) -> list[SystemSettingPublic]:
    """Все настройки; API-ключи и токены отдаются в маскированном виде."""
    rows = await repo.list_all()
    return [_to_public(r, masked=True) for r in rows]


@router.put("/settings", status_code=status.HTTP_200_OK)
async def update_settings(
    body: SettingsUpdateRequest,
    repo: SettingsRepositoryDep,
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

    try:
        await repo.upsert_values(normalized)
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return {"ok": True}
