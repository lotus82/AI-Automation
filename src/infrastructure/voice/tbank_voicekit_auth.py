"""JWT для gRPC/REST T-Bank VoiceKit (по примеру Tinkoff voicekit-examples)."""

from __future__ import annotations

import base64
import copy
import hmac
import json
from time import time
from typing import Any

TEN_MINUTES = 600


def generate_jwt(api_key: str, secret_key: str, payload: dict[str, Any], expiration_time: int = TEN_MINUTES) -> str:
    header = {
        "alg": "HS256",
        "typ": "JWT",
        "kid": api_key,
    }
    payload_copy = copy.deepcopy(payload)
    current_timestamp = int(time())
    payload_copy["exp"] = current_timestamp + expiration_time
    payload_bytes = json.dumps(payload_copy, separators=(",", ":")).encode("utf-8")
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")

    data = base64.urlsafe_b64encode(header_bytes).strip(b"=") + b"." + base64.urlsafe_b64encode(
        payload_bytes
    ).strip(b"=")

    signature = hmac.new(base64.urlsafe_b64decode(secret_key), msg=data, digestmod="sha256")
    jwt = data + b"." + base64.urlsafe_b64encode(signature.digest()).strip(b"=")
    return jwt.decode("utf-8")


def authorization_bearer(api_key: str, secret_key: str, scope: str) -> str:
    """Один заголовок ``Authorization: Bearer <jwt>``."""
    auth_payload = {
        "iss": "test_issuer",
        "sub": "test_user",
        "aud": scope,
    }
    return "Bearer " + generate_jwt(api_key, secret_key, auth_payload)


def authorization_metadata(
    api_key: str,
    secret_key: str,
    scope: str,
    *,
    as_type: type = list,
) -> list[tuple[str, str]] | dict[str, str]:
    """Метаданные gRPC или dict заголовков для HTTP (``type=dict``)."""
    token = authorization_bearer(api_key, secret_key, scope)
    meta: list[tuple[str, str]] = [("authorization", token)]
    if as_type is dict:
        return {k: v for k, v in meta}
    return as_type(meta)
