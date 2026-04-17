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
    miniapp,
    notifications,
    mis,
    mis_patient_auth,
    portal_management,
    public_store,
    questionnaires,
    registration_forms,
    schedules,
    shops,
    sites,
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
from src.infrastructure.max_bot_identity import (
    enumerate_max_bot_long_poll_org_ids,
    sync_all_max_bot_user_ids_from_stored_tokens,
)
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
    app.state.max_poll_tasks = []
    app.state.max_poll_session_cms = []
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

    app.state.max_poll_stop = asyncio.Event()

    async with AsyncSessionLocal() as bootstrap_session:
        await ensure_portal_bootstrap(bootstrap_session)
        await sync_all_max_bot_user_ids_from_stored_tokens(
            bootstrap_session,
            app.state.redis,
            app_settings=settings,
        )
        targets = await enumerate_max_bot_long_poll_org_ids(bootstrap_session)
        await bootstrap_session.commit()

    if settings.max_long_poll_organization_id is not None:
        flt = settings.max_long_poll_organization_id
        before = len(targets)
        targets = [t for t in targets if t == flt]
        logger.info(
            "MAX long poll: фильтр MAX_LONG_POLL_ORGANIZATION_ID=%s — контекстов %s → %s",
            flt,
            before,
            len(targets),
        )

    if not targets:
        logger.info(
            "MAX long poll: в БД нет MAX_BOT_TOKEN (ни в system_settings, ни в organization_settings) — "
            "задачи опроса /updates не созданы",
        )
    else:
        for org_id in targets:
            sess_cm = AsyncSessionLocal()
            poll_session = await sess_cm.__aenter__()
            app.state.max_poll_session_cms.append(sess_cm)
            uc, mx_client = build_max_long_poll_stack(
                poll_session,
                app.state.redis,
                settings,
                organization_id=org_id,
            )
            task_name = "max-long-poll-global" if org_id is None else f"max-long-poll-org-{org_id}"
            t = asyncio.create_task(
                mx_client.start_polling(
                    uc,
                    session=poll_session,
                    stop_event=app.state.max_poll_stop,
                    redis=app.state.redis,
                    app_settings=settings,
                    organization_id=org_id,
                ),
                name=task_name,
            )
            app.state.max_poll_tasks.append(t)
        logger.info(
            "Запущено задач MAX long polling: %s (опрос при MAX_USE_POLLING в соответствующих настройках)",
            len(app.state.max_poll_tasks),
        )
    try:
        yield
    finally:
        if app.state.max_poll_stop is not None:
            app.state.max_poll_stop.set()
        for t in app.state.max_poll_tasks:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
        for cm in app.state.max_poll_session_cms:
            try:
                await cm.__aexit__(None, None, None)
            except Exception:
                logger.exception("Ошибка закрытия сессии MAX long poll")
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
    application.include_router(registration_forms.router, prefix="/api")
    application.include_router(shops.router, prefix="/api")
    application.include_router(public_store.router, prefix="/api")
    application.include_router(mis.router, prefix="/api")
    application.include_router(mis_patient_auth.router, prefix="/api")
    application.include_router(mis.public_router, prefix="/api")
    application.include_router(knowledge.router, prefix="/api", tags=["knowledge"])
    application.include_router(telephony.router, prefix="/api", tags=["telephony"])
    application.include_router(dialer.router, prefix="/api", tags=["dialer"])
    application.include_router(settings_router.router, prefix="/api", tags=["settings"])
    application.include_router(max_bot.router, prefix="/api")
    application.include_router(miniapp.router, prefix="/api")
    application.include_router(miniapp.public_router, prefix="/api")
    application.include_router(miniapp.admin_router, prefix="/api")
    application.include_router(sites.router, prefix="/api")
    application.include_router(sites.public_router, prefix="/api")
    application.include_router(chats.router, prefix="/api")
    application.include_router(schedules.router, prefix="/api")
    application.include_router(notifications.router, prefix="/api")
    application.include_router(voice.router, prefix="/voice", tags=["voice"])

    return application


app = create_app()
