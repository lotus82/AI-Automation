"""Адаптер эмбеддингов на официальном async-клиенте OpenAI."""

from __future__ import annotations

from openai import AsyncOpenAI

from src.core.config import Settings
from src.infrastructure.models import KNOWLEDGE_EMBEDDING_DIM
from src.use_cases.interfaces import IEmbeddingService

# Модель по умолчанию: 1536 измерений, согласовано с колонкой vector(1536) в БД.
_EMBEDDING_MODEL = "text-embedding-3-small"


class OpenAIEmbeddingService(IEmbeddingService):
    """Векторизация текста через OpenAI Embeddings API."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        # TODO: Вынести проверку ключа в общий слой (например, при lifespan) и обрабатывать ошибки API;
        #       при отсутствии OPENAI_API_KEY используется нулевой вектор для локальных тестов без биллинга.
        self._client: AsyncOpenAI | None = None
        if settings.openai_api_key:
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def generate_embedding(self, text: str) -> list[float]:
        if not self._client:
            return [0.0] * KNOWLEDGE_EMBEDDING_DIM

        response = await self._client.embeddings.create(
            model=_EMBEDDING_MODEL,
            input=text,
            dimensions=KNOWLEDGE_EMBEDDING_DIM,
        )
        vector = response.data[0].embedding
        return [float(x) for x in vector]
