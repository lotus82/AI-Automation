"""Хэширование паролей и JWT для портала."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError as JWTInvalidTokenError

# Ограничение bcrypt на длину пароля в байтах
_BCRYPT_MAX_PASSWORD_BYTES = 72


def _password_bytes(plain: str) -> bytes:
    b = plain.encode("utf-8")
    return b[:_BCRYPT_MAX_PASSWORD_BYTES] if len(b) > _BCRYPT_MAX_PASSWORD_BYTES else b


def hash_password(plain: str) -> str:
    """Bcrypt-хэш в виде ASCII-строки (для поля ``password_hash``)."""
    return bcrypt.hashpw(_password_bytes(plain), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_password_bytes(plain), password_hash.encode("ascii"))
    except (ValueError, TypeError):
        return False


def create_portal_access_token(
    *,
    user_id: UUID,
    role: str,
    organization_id: UUID | None,
    secret: str,
    expire_minutes: int,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "org_id": str(organization_id) if organization_id else None,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expire_minutes)).timestamp()),
        "typ": "portal",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def create_mis_patient_access_token(
    *,
    patient_id: UUID,
    organization_id: UUID,
    secret: str,
    expire_minutes: int,
) -> str:
    """JWT личного кабинета пациента МИС (мессенджер MAX и др.). ``typ``: ``mis_patient``."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(patient_id),
        "role": "mis_patient",
        "org_id": str(organization_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expire_minutes)).timestamp()),
        "typ": "mis_patient",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_portal_token(token: str, secret: str) -> dict[str, Any]:
    return jwt.decode(token, secret, algorithms=["HS256"])


MINIAPP_TYP = "miniapp"


def create_miniapp_access_token(
    *,
    user_id: UUID,
    organization_id: UUID,
    chat_id: str,
    secret: str,
    expire_minutes: int = 60 * 24,
) -> str:
    """JWT для пользователя Mini App мессенджера MAX.

    ``typ``/``aud``: ``miniapp``; ``sub`` — ``MiniAppUserModel.id`` (внутренний UUID),
    ``org_id`` — организация, ``chat_id`` — идентификатор чата в мессенджере.
    """
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "org_id": str(organization_id),
        "chat_id": str(chat_id),
        "typ": MINIAPP_TYP,
        "aud": MINIAPP_TYP,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expire_minutes)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_miniapp_token(token: str, secret: str) -> dict[str, Any]:
    data = jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        audience=MINIAPP_TYP,
    )
    if data.get("typ") != MINIAPP_TYP:
        raise JWTInvalidTokenError("Неверный тип токена Mini App")
    return data


MIS_QUESTIONNAIRE_INVITE_TYP = "mis_q_invite"


def create_mis_questionnaire_invite_token(
    *,
    patient_id: UUID,
    questionnaire_id: UUID,
    organization_id: UUID,
    secret: str,
    expire_days: int = 90,
) -> str:
    """Одноразовая по смыслу ссылка на опрос для карты МИС (подпись HS256, тот же секрет, что у портала)."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "typ": MIS_QUESTIONNAIRE_INVITE_TYP,
        "pid": str(patient_id),
        "qid": str(questionnaire_id),
        "oid": str(organization_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=expire_days)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_mis_questionnaire_invite_token(token: str, secret: str) -> dict[str, Any]:
    data = jwt.decode(token, secret, algorithms=["HS256"])
    if data.get("typ") != MIS_QUESTIONNAIRE_INVITE_TYP:
        raise JWTInvalidTokenError("Неверный тип приглашения")
    return data
