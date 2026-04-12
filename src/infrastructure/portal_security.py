"""Хэширование паролей и JWT для портала."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import bcrypt
import jwt

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


def decode_portal_token(token: str, secret: str) -> dict[str, Any]:
    return jwt.decode(token, secret, algorithms=["HS256"])
