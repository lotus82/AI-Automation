"""Проверка доступности API."""

from fastapi import APIRouter, status

from src.api.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Проверка работоспособности",
)
async def health() -> HealthResponse:
    """Возвращает 200 OK, если процесс приложения отвечает."""
    return HealthResponse(status="ok")
