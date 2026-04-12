"""Точка входа FastAPI: JSON API и WebSocket (без Jinja2 и раздачи статики)."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from src.api.middleware.portal_auth_middleware import PortalAuthMiddleware
from src.api.routers import (
    admin_logs,
    auth_portal,
    bitrix,
    calls,
    chat,
    chats,
    dialer,
    health,
    knowledge,
    leads,
    max_bot,
    notifications,
    portal_management,
    questionnaires,
    schedules,
    telephony,
    trainer,
    training,
    voice,
)
from src.presentation.api.routers import chat as agent_chat_router
from src.presentation.api.routers import integrations as integrations_router
from src.api.routers import settings as settings_router
from src.api.dependencies import build_max_long_poll_stack
from src.core.config import get_settings
from src.core.logging import setup_logging
from src.infrastructure.database import AsyncSessionLocal
from src.infrastructure.portal_bootstrap import ensure_portal_bootstrap

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Жизненный цикл: логирование, async Redis для памяти диалогов, опционально MAX long polling."""
    settings = get_settings()
    setup_logging(debug=settings.debug)
    app.state.redis = Redis.from_url(
        settings.redis_uri,
        encoding="utf-8",
        decode_responses=True,
    )
    app.state.ari_stop_event = asyncio.Event()
    app.state.ari_listener_task = None
    app.state.max_poll_stop = None
    app.state.max_poll_task = None
    app.state.max_poll_session_cm = None
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
    # Long poll MAX всегда поднимаем фоновой задачей; реально дергается /updates только если
    # MAX_USE_POLLING=1 в system_settings (панель). Раньше при MAX_USE_POLLING=false в .env задача
    # не создавалась — БД «вкл» игнорировалось, бот молчал без вебхука.
    app.state.max_poll_stop = asyncio.Event()
    sess_cm = AsyncSessionLocal()
    app.state.max_poll_session_cm = sess_cm
    app.state.max_poll_session = await sess_cm.__aenter__()
    uc, mx_client = build_max_long_poll_stack(
        app.state.max_poll_session,
        app.state.redis,
        settings,
    )
    app.state.max_poll_task = asyncio.create_task(
        mx_client.start_polling(
            uc,
            session=app.state.max_poll_session,
            stop_event=app.state.max_poll_stop,
            redis=app.state.redis,
            app_settings=settings,
        ),
        name="max-long-polling",
    )
    logger.info(
        "Задача MAX long polling запущена; опрос platform-api при MAX_USE_POLLING в БД; "
        "переменная окружения MAX_USE_POLLING больше не отключает создание воркера (см. README)."
    )
    async with AsyncSessionLocal() as bootstrap_session:
        await ensure_portal_bootstrap(bootstrap_session)
    try:
        yield
    finally:
        if app.state.max_poll_stop is not None:
            app.state.max_poll_stop.set()
        if app.state.max_poll_task is not None:
            app.state.max_poll_task.cancel()
            try:
                await app.state.max_poll_task
            except asyncio.CancelledError:
                pass
        if app.state.max_poll_session_cm is not None:
            await app.state.max_poll_session_cm.__aexit__(None, None, None)
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
        version="0.13.0",
        lifespan=lifespan,
        debug=settings.debug,
    )
    # В т.ч. симулятор вебхука MAX с панели bots.html: POST /api/max/webhook с того же origin или другого порта.
    application.add_middleware(PortalAuthMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(auth_portal.router, prefix="/api")
    application.include_router(portal_management.router, prefix="/api")
    application.include_router(integrations_router.router, prefix="/api")
    application.include_router(agent_chat_router.router, prefix="/api")
    application.include_router(health.router, prefix="/api")
    application.include_router(admin_logs.router, prefix="/api")
    application.include_router(bitrix.router, prefix="/api")
    application.include_router(leads.router, prefix="/api/leads", tags=["leads"])
    application.include_router(chat.router, prefix="/api/chat", tags=["chat"])
    application.include_router(calls.router, prefix="/api")
    application.include_router(training.router, prefix="/api", tags=["training"])
    application.include_router(trainer.router, prefix="/api")
    application.include_router(questionnaires.router, prefix="/api")
    application.include_router(knowledge.router, prefix="/api", tags=["knowledge"])
    application.include_router(telephony.router, prefix="/api", tags=["telephony"])
    application.include_router(dialer.router, prefix="/api", tags=["dialer"])
    application.include_router(settings_router.router, prefix="/api", tags=["settings"])
    application.include_router(max_bot.router, prefix="/api")
    application.include_router(chats.router, prefix="/api")
    application.include_router(schedules.router, prefix="/api")
    application.include_router(notifications.router, prefix="/api")
    application.include_router(voice.router, prefix="/voice", tags=["voice"])

    return application


app = create_app()
