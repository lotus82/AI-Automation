"""Подключение к Redis (брокер задач и кэш состояния — на последующих фазах)."""

from redis.asyncio import Redis

from src.core.config import get_settings


def create_redis_client() -> Redis:
    """Создаёт клиент asyncio-redis; вызывающий код отвечает за закрытие соединения."""
    settings = get_settings()
    return Redis.from_url(
        settings.redis_uri,
        encoding="utf-8",
        decode_responses=True,
    )
