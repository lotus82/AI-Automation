"""Минимальный клиент Docker Engine API через Unix-сокет (httpx)."""

from __future__ import annotations

import os
from typing import Any

import httpx


def decode_docker_multiplexed_logs(raw: bytes) -> str:
    """Распаковка потока Docker (8 байт заголовок + фрагмент)."""
    parts: list[str] = []
    i = 0
    n = len(raw)
    while i + 8 <= n:
        size = int.from_bytes(raw[i + 4 : i + 8], "big")
        i += 8
        if size <= 0 or i + size > n:
            break
        parts.append(raw[i : i + size].decode("utf-8", errors="replace"))
        i += size
    if parts:
        return "".join(parts)
    return raw.decode("utf-8", errors="replace")


class DockerEngineClient:
    def __init__(self, *, socket_path: str, api_version: str) -> None:
        self._socket_path = socket_path
        self._api_version = api_version.strip().lstrip("v") or "1.41"

    def _base(self) -> str:
        return f"http://localhost/v{self._api_version}"

    def available(self) -> bool:
        return os.path.exists(self._socket_path)

    async def _client(self) -> httpx.AsyncClient:
        transport = httpx.AsyncHTTPTransport(uds=self._socket_path)
        return httpx.AsyncClient(transport=transport, base_url=self._base(), timeout=httpx.Timeout(120.0))

    async def list_containers(self, *, all_containers: bool = True) -> list[dict[str, Any]]:
        async with await self._client() as client:
            r = await client.get("/containers/json", params={"all": str(all_containers).lower()})
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else []

    async def container_logs(self, container_id: str, *, tail: int = 500, timestamps: bool = True) -> bytes:
        cid = container_id.strip()
        if not cid:
            raise ValueError("Пустой идентификатор контейнера")
        tail = max(1, min(tail, 20_000))
        async with await self._client() as client:
            r = await client.get(
                f"/containers/{cid}/logs",
                params={
                    "stdout": "true",
                    "stderr": "true",
                    "tail": str(tail),
                    "timestamps": str(timestamps).lower(),
                },
            )
            r.raise_for_status()
            return r.content
