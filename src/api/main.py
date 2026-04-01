"""Точка входа FastAPI: JSON API и WebSocket (без Jinja2 и раздачи статики)."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from src.api.routers import calls, chat, dialer, health, leads, telephony, training, voice
from src.core.config import get_settings
from src.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Жизненный цикл: логирование, async Redis для памяти диалогов."""
    settings = get_settings()
    setup_logging(debug=settings.debug)
    app.state.redis = Redis.from_url(
        settings.redis_uri,
        encoding="utf-8",
        decode_responses=True,
    )
    app.state.ari_stop_event = asyncio.Event()
    app.state.ari_listener_task = None
    if (
        (settings.asterisk_url or "").strip()
        and (settings.asterisk_ari_user or "").strip()
        and (settings.asterisk_ari_password or "").strip()
    ):
        from src.infrastructure.telephony.ari_client import run_ari_event_listener

        app.state.ari_listener_task = asyncio.create_task(
            run_ari_event_listener(settings, app.state.redis, app.state.ari_stop_event),
            name="ari-event-listener",
        )
    try:
        yield
    finally:
        if app.state.ari_listener_task is not None:
            app.state.ari_stop_event.set()
            app.state.ari_listener_task.cancel()
            try:
                await app.state.ari_listener_task
            except asyncio.CancelledError:
                pass
        await app.state.redis.aclose()


def create_app() -> FastAPI:
    """Фабрика приложения (удобно для тестов и разных конфигураций)."""
    settings = get_settings()
    application = FastAPI(
        title="Sales AI Agent API",
        version="0.11.0",
        lifespan=lifespan,
        debug=settings.debug,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health.router, prefix="/api")
    application.include_router(leads.router, prefix="/api/leads", tags=["leads"])
    application.include_router(chat.router, prefix="/api/chat", tags=["chat"])
    application.include_router(calls.router, prefix="/api")
    application.include_router(training.router, prefix="/api", tags=["training"])
    application.include_router(telephony.router, prefix="/api", tags=["telephony"])
    application.include_router(dialer.router, prefix="/api", tags=["dialer"])
    application.include_router(voice.router, prefix="/voice", tags=["voice"])

    return application


app = create_app()
