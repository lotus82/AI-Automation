# SPA (React + Vite + React Router + Tailwind)

Каркас одностраничного приложения рядом с легаси `frontend/*.html`. Сборка: `npm run build` → каталог `dist/` для раздачи через Nginx.

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
    │   └── layout/
    │       └── Sidebar.jsx
    └── pages/
        ├── DashboardPage.jsx
        ├── QAPage.jsx
        ├── AITrainerPage.jsx
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
| `/`             | Дашборд                           |
| `/qa-analytics` | ИИ-контроль (QA)                  |
| `/ai-trainer`   | ИИ-тренер                         |
| `/leadgen`      | ИИ-лидогенератор                  |
| `/tester`       | Тестирование голоса               |
| `/scenarios`    | Сценарии                          |
| `/telephony`    | Телефония                         |
| `/settings`     | Настройки                         |
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
