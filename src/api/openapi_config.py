"""Описание API для OpenAPI 3.0 (Swagger UI / ReDoc) и доработка схемы."""

from __future__ import annotations

from typing import Any

# Текст в карточке API в Swagger; поддерживает Markdown
API_DESCRIPTION = """
REST API бэкенда (панель, Mini App, публичные сценарии, интеграции).

**Авторизация панели**  
Получите `access_token` через **`POST /api/auth/login`**. Во всех защищённых эндпоинтах передавайте заголовок
`Authorization: Bearer <access_token>`.  
В Swagger: кнопка **Authorize** → в поле *PortalBearer* вставьте только токен (без префикса `Bearer`).

**Параметр организации**  
У многих маршрутов в query есть необязательный `organization_id` (UUID). Для **super_admin** при работе
с сущностями организации он обязателен; у остальных ролей берётся текущая организация из токена.

**Публичные маршруты** (без токена) отмечены в описаниях: опросы, публичный магазин, `GET /api/health` и т.д.

Схема в формате **OpenAPI 3.0.3** доступна на **`/openapi.json`**; интерактивно — **`/docs`** (Swagger) и **`/redoc`**.
""".strip()

# Группировка тегов в Swagger (имена тегов должны совпадать с `tags=[...]` в роутерах при возможности)
OPENAPI_TAG_METADATA: list[dict[str, str]] = [
    {"name": "health", "description": "Проверка работоспособности"},
    {"name": "auth", "description": "Вход портала, refresh, смена пароля"},
    {"name": "portal", "description": "Пользователи, организации, настройки портала"},
    {"name": "settings", "description": "Настройки приложения (API-ключи и т.д.)"},
    {"name": "integrations", "description": "Интеграции (n8n и др.)"},
    {"name": "documents", "description": "Модуль «Читатель»: документы, узлы, загрузка .txt, публичная выдача"},
    {"name": "documents-public", "description": "Публичная выдача дерева документа (Mini App)"},
    {"name": "sites", "description": "Сайты и страницы для Mini App"},
    {"name": "sites-public", "description": "Публичные страницы сайта"},
    {"name": "miniapp", "description": "Авторизация и конфиг MAX Mini App"},
    {"name": "bookings", "description": "Запись на приём, слоты, публичное API"},
    {"name": "shops", "description": "Магазин, каталог, заказы"},
    {"name": "mis", "description": "МИС: врач, пациент, публичные API"},
    {"name": "knowledge", "description": "База знаний"},
    {"name": "questionnaires", "description": "Опросы и оценка ответов"},
    {"name": "training", "description": "Сценарии и тренер"},
    {"name": "chat", "description": "Чат, диалоги, память сессий"},
    {"name": "voice", "description": "Голос: WebSocket, STT/TTS"},
    {"name": "telephony", "description": "Телефония"},
    {"name": "dialer", "description": "Автодозвон, очередь"},
    {"name": "leads", "description": "Лидген"},
    {"name": "calls", "description": "Звонки и аналитика"},
    {"name": "chats", "description": "Сессии чатов"},
    {"name": "max_bot", "description": "MAX бот, вебхуки"},
    {"name": "bitrix", "description": "Bitrix24"},
    {"name": "admin_logs", "description": "Логи (админ)"},
    {"name": "notifications", "description": "Уведомления"},
    {"name": "schedules", "description": "Расписания сценариев"},
    {"name": "forms", "description": "Формы, события, регистрация"},
    {"name": "public_store", "description": "Публичная витрина (магазин)"},
    {"name": "trainer", "description": "AI Trainer"},
]

_CONTACT: dict[str, str] = {
    "name": "API",
}


def _dedupe_tag_metadata(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for it in items:
        n = it.get("name", "")
        if n in seen:
            continue
        seen.add(n)
        out.append(it)
    return out


def build_openapi_schema(app: Any) -> dict[str, Any]:
    """Строит OpenAPI 3.0.3, добавляет схему безопасности для ручного ввода JWT в Swagger."""
    from fastapi.openapi.utils import get_openapi

    if getattr(app, "openapi_schema", None):
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version="3.0.3",
        summary=getattr(app, "summary", None) or "Lotus / Sales AI API",
        description=app.description,
        routes=app.routes,
        tags=_dedupe_tag_metadata(OPENAPI_TAG_METADATA),
        contact=_CONTACT,
    )

    components = schema.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    security_schemes["PortalBearer"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "JWT портала: ответ `POST /api/auth/login` → поле `access_token`.",
    }

    app.openapi_schema = schema
    return schema
