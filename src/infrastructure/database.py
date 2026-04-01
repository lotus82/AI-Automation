"""Асинхронный движок SQLAlchemy и фабрика сессий."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config import get_settings

_settings = get_settings()

# Движок и фабрика сессий создаются при импорте модуля (ленивое пересоздание не требуется на фазе 1)
engine: AsyncEngine = create_async_engine(
    _settings.postgres_uri,
    echo=_settings.debug,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Выдаёт сессию для DI; после успешного запроса фиксирует транзакцию."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
