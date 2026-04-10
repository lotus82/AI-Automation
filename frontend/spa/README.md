# SPA (React + Vite + React Router + Tailwind)

Каркас одностраничного приложения рядом с легаси `frontend/*.html`. Сборка: `npm run build` → каталог `dist/` для раздачи через Nginx.

## Сборка на VPS без Node.js (рекомендуется)

Сборка Vite выполняется **внутри Docker** (образ **Node 22**), на хосте достаточно **Docker Engine** + **Docker Compose v2**.

Из **корня репозитория** (не из `frontend/spa`):

```bash
# только образ панели (не нужен .env с POSTGRES и не поднимается БД)
docker compose -f docker-compose.frontend.yml build

# готовый образ по умолчанию: sales-ai-frontend:latest
docker images | grep sales-ai-frontend
```

Свой тег или registry:

```bash
FRONTEND_IMAGE=myregistry.io/company/sales-ui:1.0 docker compose -f docker-compose.frontend.yml build
```

В составе полного продакшен-стека тот же Dockerfile:

```bash
docker compose -f docker-compose.prod.yml build frontend
```

Конфигурация: **`docker-compose.frontend.yml`**, **`frontend/Dockerfile.prod`**, прокси **`/api`** и **`/voice`** на сервис **`web`** — см. **`frontend/nginx.conf`** (в `docker-compose.prod.yml` контейнеры в одной сети).

## Локальная сборка на машине (Node.js)

Нужны **Node.js ≥ 18** и **npm ≥ 8** (рекомендуется **Node 20 или 22 LTS**). На Ubuntu из репозитория часто ставится **Node 12** — с ним `vite build` падает (`Unexpected reserved word` на `await`).

**Обновление Node (nvm):**

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc
cd frontend/spa && nvm install && nvm use   # читает .nvmrc (22)
npm ci && npm run build
```

Или пакет **NodeSource** — см. [NodeSource distributions](https://github.com/nodesource/distributions).

## Структура

```
frontend/spa/
├── index.html
├── package.json
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
├── README.md
└── src/
    ├── main.jsx              # точка входа + BrowserRouter
    ├── App.jsx               # Routes + useBitrixAuth()
    ├── index.css             # Tailwind
    ├── api/
    │   └── client.js         # axios + заголовки Битрикс24
    ├── store/
    │   └── bitrixAuthStore.js
    ├── hooks/
    │   └── useBitrixAuth.js
    ├── layouts/
    │   └── Layout.jsx        # Sidebar + <Outlet />
    ├── components/
    │   ├── layout/
    │   │   └── Sidebar.jsx
    │   └── trainer/
    │       ├── CallAnalysisTab.jsx
    │       └── TrainerScenariosPanel.jsx
    └── pages/
        ├── QAPage.jsx
        ├── AITrainerPage.jsx
        ├── IntegrationsPage.jsx
        └── LeadgenPage.jsx
```

## Скрипты

- `npm install`
- `npm run dev` — Vite, прокси `/api` → `http://127.0.0.1:8000`
- `npm run build`
- `npm run preview` — проверка production-сборки

## Маршруты

| Путь            | Страница                          |
|-----------------|-----------------------------------|
| `/`             | редирект → `/qa-analytics`        |
| `/qa-analytics` | ИИ-контроль (QA): звонки, `?tab=analysis` — BANT/MEDDIC |
| `/ai-trainer`   | ИИ-тренер: симуляция, `?tab=scenarios` — сценарии |
| `/leadgen`      | ИИ-лидогенератор + телефония      |
| `/tester`       | Тестирование голоса               |
| `/scenarios`    | редирект → `/ai-trainer?tab=scenarios` |
| `/telephony`    | редирект → `/leadgen`             |
| `/integrations` | Интеграции (внешние системы)       |
| `/settings`     | Настройки                         |
| `/logs`         | Логи Docker (отладка VPS)         |
| `/knowledge`    | База знаний                       |
| `/bots`         | Боты                              |
| `/schedule`     | Расписание                        |

## Битрикс24 (iframe)

Параметры из query (`DOMAIN`, `APP_SID`, `AUTH_ID`, …) читает `useBitrixAuth` и кладёт в Zustand. Axios добавляет заголовки `X-Bitrix-Domain`, `X-Bitrix-App-Sid`, `X-Bitrix-Auth-Id`. На FastAPI при необходимости добавьте приём этих заголовков в зависимостях.

## Nginx

Пример `location /` для статики SPA и History API (пути без `#`). Подставьте свой `root` к `dist`.

```nginx
# Статика React (после npm run build)
location / {
    root /var/www/sales-ai-spa/dist;
    try_files $uri $uri/ /index.html;

    # Разрешить встраивание в iframe Битрикс24 (при необходимости ужесточьте frame-ancestors)
    add_header Content-Security-Policy "frame-ancestors 'self' https://*.bitrix24.ru https://*.bitrix24.com https://*.bitrix24.de" always;
    add_header X-Content-Type-Options "nosniff" always;

    # Снять ограничение X-Frame-Options, если был задан выше по серверу
    add_header X-Frame-Options "" always;
}

# Проксирование API на FastAPI (префикс как в приложении)
location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    # Проброс заголовков из axios (Битрикс iframe)
    proxy_set_header X-Bitrix-Domain $http_x_bitrix_domain;
    proxy_set_header X-Bitrix-App-Sid $http_x_bitrix_app_sid;
    proxy_set_header X-Bitrix-Auth-Id $http_x_bitrix_auth_id;
}
```

**Примечание:** `frame-ancestors` в `Content-Security-Policy` задаёт, кто может встроить страницу; `X-Frame-Options: DENY` у родительского сервера сломает iframe — сбросьте на уровне этого `location`, как в примере.
