"""Адаптер эмбеддингов: ключ OpenAI из настроек БД (кэш Redis) с запасным **OPENAI_API_KEY** из env."""

from __future__ import annotations

from openai import AsyncOpenAI

from src.core.config import Settings
from src.domain import system_setting_keys as sk
from src.infrastructure.models import KNOWLEDGE_EMBEDDING_DIM
from src.use_cases.interfaces import IEmbeddingService, ISettingsRepository

# Модель по умолчанию: 1536 измерений, согласовано с колонкой vector(1536) в БД.
_EMBEDDING_MODEL = "text-embedding-3-small"


class OpenAIEmbeddingService(IEmbeddingService):
    """Векторизация текста через OpenAI Embeddings API."""

    def __init__(
        self,
        settings: Settings,
        settings_repo: ISettingsRepository | None = None,
    ) -> None:
        self._settings = settings
        self._repo = settings_repo
        self._client: AsyncOpenAI | None = None
        self._cached_key_fingerprint: str = ""

    async def _api_key(self) -> str:
        if self._repo is not None:
            raw = await self._repo.get_value(sk.OPENAI_API_KEY)
            if raw is not None and raw.strip():
                return raw.strip()
        return (self._settings.openai_api_key or "").strip()

    async def generate_embedding(self, text: str) -> list[float]:
        key = await self._api_key()
        fp = f"{len(key)}:{key[:8]}"
        if not key:
            return [0.0] * KNOWLEDGE_EMBEDDING_DIM
        if fp != self._cached_key_fingerprint or self._client is None:
            self._client = AsyncOpenAI(api_key=key)
            self._cached_key_fingerprint = fp

        response = await self._client.embeddings.create(
            model=_EMBEDDING_MODEL,
            input=text,
            dimensions=KNOWLEDGE_EMBEDDING_DIM,
        )
        vector = response.data[0].embedding
        return [float(x) for x in vector]
