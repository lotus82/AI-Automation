"""Логи Docker-контейнеров для отладки на VPS (токен + сокет в compose)."""

from __future__ import annotations

import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from src.api.dependencies import SettingsDep
from src.api.schemas.admin_logs import ContainerLogItem, ContainerLogsResponse, ContainersListResponse
from src.core.config import Settings
from src.infrastructure.docker_engine_client import DockerEngineClient, decode_docker_multiplexed_logs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/container-logs", tags=["admin-logs"])


def _verify_logs_token(
    settings: Settings,
    x_admin_logs_token: str | None,
) -> None:
    expected = (settings.admin_logs_token or "").strip()
    if not expected:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Просмотр логов отключён: задайте ADMIN_LOGS_TOKEN в .env на сервере.",
        )
    got = (x_admin_logs_token or "").strip()
    if got != expected:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Неверный или отсутствует заголовок X-Admin-Logs-Token.",
        )


def _client_for_settings(settings: Settings) -> DockerEngineClient:
    return DockerEngineClient(
        socket_path=settings.docker_socket_path,
        api_version=settings.docker_api_version,
    )


@router.get("/containers", response_model=ContainersListResponse)
async def list_containers(
    settings: SettingsDep,
    x_admin_logs_token: Annotated[str | None, Header(alias="X-Admin-Logs-Token")] = None,
) -> ContainersListResponse:
    _verify_logs_token(settings, x_admin_logs_token)
    de = _client_for_settings(settings)
    if not de.available():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Нет доступа к Docker-сокету ({settings.docker_socket_path}). Смонтируйте его в контейнер web.",
        )
    try:
        raw_list = await de.list_containers(all_containers=True)
    except httpx.HTTPStatusError as e:
        logger.warning("docker list containers HTTP error: %s", e)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"Docker API: {e.response.status_code}",
        ) from e
    except OSError as e:
        logger.warning("docker socket error: %s", e)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Ошибка сокета Docker: {e!s}",
        ) from e
    except Exception as e:
        logger.exception("docker list failed")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"Docker: {e!s}",
        ) from e

    items: list[ContainerLogItem] = []
    for row in raw_list:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("Id") or "")
        if not cid:
            continue
        names_raw = row.get("Names") or []
        names: list[str] = []
        if isinstance(names_raw, list):
            for n in names_raw:
                if isinstance(n, str):
                    names.append(n.lstrip("/"))
        items.append(
            ContainerLogItem(
                id=cid,
                short_id=cid[:12],
                names=names,
                image=str(row.get("Image") or ""),
                state=str(row.get("State") or ""),
                status=str(row.get("Status") or ""),
            )
        )
    items.sort(key=lambda x: (x.names[0] if x.names else x.short_id).lower())
    return ContainersListResponse(containers=items)


@router.get("/{container_id}/logs", response_model=ContainerLogsResponse)
async def get_container_logs(
    container_id: str,
    settings: SettingsDep,
    x_admin_logs_token: Annotated[str | None, Header(alias="X-Admin-Logs-Token")] = None,
    tail: Annotated[int, Query(ge=1, le=20_000)] = 500,
    timestamps: Annotated[bool, Query()] = True,
) -> ContainerLogsResponse:
    _verify_logs_token(settings, x_admin_logs_token)
    de = _client_for_settings(settings)
    if not de.available():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Нет доступа к Docker-сокету ({settings.docker_socket_path}).",
        )
    try:
        raw = await de.container_logs(container_id, tail=tail, timestamps=timestamps)
        text = decode_docker_multiplexed_logs(raw)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Контейнер не найден") from e
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"Docker API: {e.response.status_code}",
        ) from e
    except OSError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.exception("docker logs failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
    return ContainerLogsResponse(text=text)
