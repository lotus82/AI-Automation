# OpenAPI 3.0 и тестирование API

Сервис FastAPI публикует интерактивную спецификацию и схему **OpenAPI 3.0.3**.

| Ресурс | URL |
|--------|-----|
| **Swagger UI** (вызовы «Try it out») | `http://<хост>:<порт>/docs` |
| **ReDoc** (удобное чтение) | `http://<хост>:<порт>/redoc` |
| **JSON-схема** | `http://<хост>:<порт>/openapi.json` |

В Docker/проде за **Nginx** к бэкенду путь к документации тот же относительно корня (например `https://example.com/docs`).

## Авторизация в Swagger

1. Выполните `POST /api/auth/login` с логином/паролем (тело подсказано в схеме).
2. Скопируйте `access_token` из ответа.
3. Нажмите **Authorize** вверху Swagger, выберите **PortalBearer** и вставьте **только токен** (без приставки `Bearer `).
4. Вызывайте защищённые маршруты; заголовок `Authorization` подставит Swagger.

Публичные эндпоинты (опросы, `GET /api/health`, часть ` /api/public/… ` и т.д.) токен не требуют.

## Скачать схему

```bash
curl -sS "http://127.0.0.1:8000/openapi.json" -o openapi.json
```

Контур безопасности `PortalBearer` объявлен в `components.securitySchemes`; при генерации клиентов (openapi-generator, Orval и т.д.) используйте эту схему.

## Код

Описание и теги: `src/api/openapi_config.py`. Подключение: `src/api/main.py` (функция `build_openapi_schema`).  
Middleware `PortalAuthMiddleware` пропускает `/docs`, `/redoc` и `/openapi.json` без JWT.
