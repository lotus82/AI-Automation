# AI Voice & Text Agent (отдел продаж)

Сервис для голосового и текстового ИИ-агента отдела продаж. **Текущее состояние: фаза 16** — на панели **`bots.html`** добавлен **режим отладки MAX**: симулятор **`POST /api/max/webhook`**, поток логов **`WS /api/ws/logs`** (модули вебхука, **`ProcessTextMessageUseCase`**, **`dynamic_llm`** / OpenAI-совместимый LLM), место под виджет MAX. Сохранена **фаза 15** — персистентная история чатов (**`chat_messages`** в PostgreSQL), лимит контекста LLM **`MAX_CONTEXT_LIMIT`**, мониторинг (**`WS /api/ws/monitoring`**), REST **`GET /api/chats`**. Сохранена **фаза 14** — **MAX** (VK): вебхук **`POST /api/max/webhook`**, токен **`MAX_BOT_TOKEN`**, исходящие сообщения через **`httpx`**. Бот MAX использует тот же **`ProcessTextMessageUseCase`**, что текстовый чат и голос (промпт **`DEFAULT_CONSULTANT_PROMPT`**, RAG, **`record_lead`** → Bitrix24, **`session_id = str(chat_id)`**). Сохранена **фаза 13**: **SaluteSpeech (Сбер SmartSpeech)** для потокового STT/TTS в Pipecat: **`SaluteSpeechAuthManager`** (OAuth `ngw.devices.sberbank.ru`, кэш токена в **Redis**, TTL **25 мин**), кастомные **`SaluteSpeechSTTService`** и **`SaluteSpeechTTSService`** на **`grpc.aio`** (RPC **`Recognize`** / **`Synthesize`**, хост **`SALUTESPEECH_GRPC_TARGET`**, обычно **smartspeech.sber.ru:443**). Proto см. **`src/infrastructure/voice/sber_protos/`**. Ключ **`SALUTESPEECH_AUTH_KEY`**, **`SALUTESPEECH_SCOPE`**, голос **`SALUTESPEECH_VOICE`** — в **`.env`** и в **`system_settings`** (миграция **`006`**). Сохранены **фазы 5–12**. Локальные Whisper/Torch/CUDA **не используются**.

---

## ВНИМАНИЕ: ограничения VPS (только CPU, без GPU)

**СТРОГО ЗАПРЕЩЕНО** добавлять в `requirements.txt` (или `pyproject.toml`) тяжёлые ML-стеки и CUDA-зависимости, в частности: **`torch` (PyTorch)**, **`tensorflow`**, **`transformers`**, а также любые сборки с **GPU/CUDA**. Целевое развёртывание — **ресурсно ограниченный VPS без видеокарты**.

- Генерация текста и эмбеддинги выполняются **только через внешние API** (например, OpenAI).
- Допустимы **очень лёгкие** CPU-библиотеки (например, чистый Python или при необходимости узкоспециализированный **CPU-only** runtime — по отдельному решению).
- **Нельзя** подключать пакеты, тянущие за собой CUDA или многогигабайтные модели в образ приложения.
- Зависимость **`pipecat-ai`** зафиксирована на **0.0.60**: в core нет **torch/transformers**; не ставьте extras вроде **`silero`**, **`whisper`**, **`moondream`**, **`ultravox`** — они тянут тяжёлые пакеты.

Нарушение этого правила ломает задуманную экономику инфраструктуры и не допускается без явного изменения архитектуры.

---

## Голосовой пайплайн (фаза 5)

Поток: **клиент (WebSocket, бинарный Protobuf)** → **Deepgram** (распознавание, **VAD в облаке**) → **`LLMUserResponseAggregator`** вызывает **`ProcessTextMessageUseCase.execute(...)`** → **TTS** → обратно клиенту.

- **Режим консультанта (по умолчанию)**: ИИ — продавец; системный промпт и RAG как в текстовом чате; инструмент **`record_lead`** доступен.
- **Режим тренажёра**: query **`mode=trainer`** и **`scenario_id=<UUID>`**; ИИ играет клиента по полям сценария (**`client_persona_prompt`**, **`objections_to_raise`**); RAG и CRM отключены. Опционально **`manager_name`** — попадает в Redis и в отчёт тренера.
- **Память**: тот же **`session_id`**, что и у **`POST /api/chat/text`**; каждое сообщение пишется в **Redis** (TTL) и в **PostgreSQL** (**`chat_messages`**). В LLM подмешиваются последние **`MAX_CONTEXT_LIMIT`** реплик; полный транскрипт для ОКК читается из БД (с fallback на Redis для старых сессий).
- **Прерывания**: при событии начала речи Deepgram (`vad_events`) в очередь задачи ставится **`StartInterruptionFrame`**; в **`PipelineParams`** включено **`allow_interruptions=True`**.
- **WebSocket**: `GET ws://.../voice/stream?session_id=<uuid>&mode=consultant|trainer&scenario_id=<uuid>&manager_name=...` (параметры кроме **`session_id`** опциональны; для **`trainer`** обязателен **`scenario_id`**).

Проверка голоса через панель см. раздел **«Фронтенд и Nginx»** ниже. Альтернатива — любой клиент с **Protobuf**-кадрами Pipecat ([пример websocket-server](https://github.com/pipecat-ai/pipecat/tree/v0.0.60/examples/websocket-server)).

### Как протестировать звонок с микрофона (`tester.html`)

1. Откройте **`http://localhost:8080/tester.html`** (или ваш домен по **HTTPS**). Страница должна быть с **localhost** / **127.0.0.1** / **HTTPS**, иначе браузер не даст микрофон.
2. В **«Настройки»** сохраните ключи: для SaluteSpeech — **Authorization Key**; для **TTS по умолчанию (OpenAI)** — **`OPENAI_API_KEY`** в **`.env`** контейнера **`web`** или ключ OpenAI в панели (иначе ответ агента не синтезируется). При **`VOICE_TTS_PROVIDER=salutespeech`** нужен только ключ Сбера.
3. В **Docker Compose** задайте провайдеры голоса, например: **`VOICE_STT_PROVIDER`**, **`VOICE_TTS_PROVIDER`** (`salutespeech` и/или `deepgram` / `openai` / `elevenlabs`). После правок **`docker compose up -d --build web`** (или перезапуск **`web`**).
4. Нажмите **«Начать звонок»**. Если сокет закроется с **кодом 1011**, в логе страницы теперь может отображаться краткая **причина**; полный traceback смотрите в логах: **`docker compose logs web -f`** (или **`docker compose logs -f web`**).
5. Частые причины **1011**: нет **`OPENAI_API_KEY`** при **`VOICE_TTS_PROVIDER=openai`**; ошибка OAuth или WebSocket к **SaluteSpeech**; несовпадение формата REST TTS; сбой **RAG/LLM** при первой реплике.

### SaluteSpeech (фаза 13)

- **Назначение**: STT и/или TTS через облако **Сбер SaluteSpeech** без локальных моделей. Переключение: **`VOICE_STT_PROVIDER=salutespeech`** и/или **`VOICE_TTS_PROVIDER=salutespeech`** (остальные комбинации с Deepgram/OpenAI/ElevenLabs допустимы).
- **Ключ Studio**: в личном кабинете [Studio](https://developers.sber.ru/studio/login) сгенерируйте **Authorization Key** и укажите его в **`SALUTESPEECH_AUTH_KEY`** (или в панели **`SALUTESPEECH_AUTH_KEY`**). Формат **`client_id:client_secret`** в строке тоже поддерживается (будет закодирован в Base64).
- **OAuth**: **`POST https://ngw.devices.sberbank.ru:9443/api/v2/oauth`** с заголовками **`Authorization: Basic …`**, **`RqUID`** (UUID) и телом **`scope=…`** (по умолчанию **`SALUTE_SPEECH_PERS`**). Токен доступа кэшируется в Redis (**25 мин**); источник значений scope — env или **`system_settings`**.
- **STT**: потоковое **gRPC** **`Recognize`** (`smartspeech.recognition.v2`), первое сообщение — **`RecognitionOptions`** (флаги **`OptionalBool`**: multi-utterance, partial results), далее **`audio_chunk`** (PCM **S16LE**, **16 kHz**). Ответы — **`RecognitionResponse`**: ветка **`transcription`** с **`results`** и **`eou`**; промежуточные гипотезы → **`InterimTranscriptionFrame`**, финал (**`eou=true`**) → **`TranscriptionFrame`**. Публичного WebSocket STT у Сбера нет; REST для низкой задержки не используется.
- **TTS**: **gRPC** **`Synthesize`** (унарный запрос + поток **`SynthesisResponse.data`**). Выход для Pipecat — **`TTSAudioRawFrame`** при **24 kHz** (линейный ресэмплинг с частоты, выведенной из имени голоса, напр. **`Ost_24000`** → **24 kHz**).
- **TLS на VPS (Beget и др.)**: если **`httpx`** / **`websockets`** падают на проверке цепочки до **ngw** или **smartspeech**, по умолчанию **`SALUTESPEECH_OAUTH_VERIFY_SSL=false`** и **`SALUTESPEECH_SMARTSPEECH_VERIFY_SSL=false`**. **# TODO (рус.):** для продакшена установите доверенные корневые сертификаты **Минцифры** в образ или ОС (например, пакет **`ca-certificates`** + ручная установка корней НУЦ / инструкции провайдера VPS), затем включите **`true`** на обоих флагах и перезапустите контейнер **`web`**.

---

## Фронтенд и Nginx (фаза 8)

- **Каталог**: корневой **`frontend/`** — **`index.html`**, **`settings.html`**, **`bots.html`** (мониторинг + отладка MAX), **`telephony.html`**, **`tester.html`**, **`scenarios.html`**, **`static/js/settings.js`**, **`bots_app.js`**, **`debug_app.js`**. Таблица звонков: **`fetch("/api/calls")`**; настройки: **`fetch("/api/settings")`**. В настройках отдельное поле **«Дополнение для текстовых ботов MAX и Telegram»** (`TEXT_BOT_SYSTEM_SUPPLEMENT`) — дописывается к системному промпту при вызовах сценария из MAX (вебхук и long polling); для будущего Telegram-роутера нужно передавать тот же флаг **`append_text_messenger_system_supplement=True`** в **`ProcessTextMessageUseCase.execute`**.
- **Docker Compose**: сервис **`frontend`** (образ **`nginx:alpine`**) публикует **`8080:80`**. Откройте **`http://localhost:8080/`** — запросы к **`/api/...`** и **`/voice/...`** уходят на внутренний сервис **`web:8000`** (см. **`frontend/nginx.conf`**). WebSocket: **`Upgrade`** / **`Connection`** для **`/voice/stream`** и для **`/api/ws/`** (мониторинг ботов и поток логов **`/api/ws/logs`**). Путь **`/api/max/webhook`** обрабатывается **`location /api/`**.
- **# TODO (MAX Messenger, рус.):** API доставки вебхуков MAX **строго** ожидает **HTTPS (порт 443)** и **доверенный** SSL-сертификат (например **Let's Encrypt**). На **порту 80** или с **самоподписанным** сертификатом платформа может **тихо** не доставлять события; для продакшена указывайте публичный **https://** URL вебхука.
- **Сервис `web`**: с хоста **порт 8000 не проброшен** (имитация продакшена); при отладке можно раскомментировать **`ports: "8000:8000"`** в **`docker-compose.yml`**.
- **Микрофон в браузере**: страница должна открываться с **`localhost`**, **`127.0.0.1`** или **HTTPS**.
- **CORS**: в **`src/api/main.py`** включён **`allow_origins=["*"]`** для удобства локальной разработки (например, статика с другого порта).

---

## MAX Messenger (фаза 14)

- **Назначение**: текстовый бот в официальном деловом мессенджере **MAX** (VK) с **той же** бизнес-логикой, что у голосового и веб-чата: **`ProcessTextMessageUseCase`** (системный промпт **`DEFAULT_CONSULTANT_PROMPT`** + опционально **`TEXT_BOT_SYSTEM_SUPPLEMENT`** из панели настроек для правил формата ответа в мессенджере, RAG по векторной **`knowledge_items`**, вызов инструмента **`record_lead`** и передача лида в **Bitrix24** при заданном **`BITRIX24_WEBHOOK_URL`**; история — **Redis** + **`chat_messages`**, см. фазу **15**).
- **Токен**: ключ **`MAX_BOT_TOKEN`** в панели **`settings.html`** / **`system_settings`** (миграция **`009`**); маскируется в **`GET /api/settings`**. Дополнительно можно задать **`MAX_BOT_TOKEN`** в **`.env`**: используется, если в БД значение пустое; непустое значение в панели имеет приоритет.
- **Вебхук (продакшен)**: **`POST /api/max/webhook`** — см. **`src/api/routers/max_bot.py`**. Входящие события **`message_created`** и **`message_callback`** (payload кнопки) разбираются в **`parse_max_webhook_incoming`**; идентификатор чата **`chat_id`** становится **`session_id`** для памяти и мониторинга. Требуется публичный **HTTPS** (см. README про ngrok / домен).
- **Long polling (локальная отладка, Docker без внешнего HTTPS)**: фоновая задача в **`lifespan`** вызывает **`MaxMessengerClient.start_polling`** — опрос **`GET https://platform-api.max.ru/updates`** с заголовком **`Authorization: <токен>`** (см. [документацию MAX](https://dev.max.ru/docs-api/methods/GET/updates)). Каждое обновление обрабатывается **так же**, как тело вебхука: **`ProcessTextMessageUseCase.execute`** → **`send_message`**. По правилам платформы **Webhook и long polling одновременно использовать нельзя** — для продакшена отключайте опрос и подписывайтесь на Webhook.
- **Переменная `MAX_USE_POLLING` в `.env`**: по умолчанию **включена** (`true`); при **`false`** задача long polling **не создаётся** (типичный продакшен только с Webhook). В панели настроек ключ **`MAX_USE_POLLING`** в **`system_settings`** (миграция **`011`**) — чекбокс «Использовать Long Polling»: при **`0`** в БД цикл **не дергает** API (пауза без перезапуска контейнера). Чтобы не поднимать воркер вообще, задайте **`MAX_USE_POLLING=false`** в окружении.
- **Исходящие сообщения**: **`MaxMessengerClient.send_message`** — **`POST https://platform-api.max.ru/messages?chat_id=…`** с **`Authorization: <токен>`** и телом **`{"text": "…"}`** (как в [документации MAX](https://dev.max.ru/docs-api/methods/POST/messages)). База задаётся **`MAX_PLATFORM_API_BASE`** (по умолчанию **`https://platform-api.max.ru`**). Переменная **`MAX_API_BASE`** в **`.env`** сохранена для совместимости, на отправку не влияет.

Пример для администратора (команды в комментариях на русском; уточните URL и формат тела в [документации MAX](https://dev.max.ru/)):

```bash
# Пример: зарегистрировать вебхук у Bot API MAX (подставьте токен и свой HTTPS-домен):
# curl -X POST "https://api.max.ru/botВАШ_ТОКЕН/setWebhook" \
#   -H "Content-Type: application/json" \
#   -d '{"url":"https://example.com/api/max/webhook"}'
```

---

## Мониторинг чатов и персистентность (фаза 15)

- **Таблица** **`chat_messages`**: **`id`**, **`session_id`**, **`role`** (`user` / `assistant`), **`content`**, **`user_display`** (опционально, имя из MAX), **`created_at`**. Миграция **`010_chat_persist`**; общая для MAX, **`POST /api/chat/text`**, голоса и будущего Telegram.
- **`HybridChatMemoryRepository`**: при **`save_message`** пишет в Redis и в PostgreSQL; **`get_history(session_id, limit=N)`** для LLM берёт последние **N** сообщений из БД (если пусто — fallback на Redis). Для ОКК **`get_history(session_id)`** без лимита отдаёт полную цепочку из БД.
- **`MAX_CONTEXT_LIMIT`**: целое **1…200**, по умолчанию **10**, в **`system_settings`** и на панели настроек; читает **`ProcessTextMessageUseCase`**.
- **`IChatMonitoringPublisher`**: реализация **`ChatEventsBroadcaster`** (**`src/infrastructure/monitoring/chat_events_broadcaster.py`**). После каждой пары реплик (user + assistant) сценарий рассылает JSON **`{type, session_id, role, content, user_info}`** всем клиентам **`WS /api/ws/monitoring`**.
- **REST**: **`GET /api/chats`** — список сессий с превью; **`GET /api/chats/{session_id}`** — полная история.
- **Панель** **`bots.html`**: таблица сессий, WebSocket-обновления, модальное окно истории по клику на строку.

---

## Отладка MAX и Docker (фаза 16)

### Инструменты на панели «Боты»

- Включите **«Режим отладки»** на **`bots.html`**: откроются три панели (сетка на широком экране, колонка на узком).
- **Панель A** — контейнер **`#bots-max-widget-root`**: сюда вручную вставляется официальный JS-сниппет виджета MAX (см. комментарий `# TODO` в HTML и [документацию MAX](https://dev.max.ru/)).
- **Панель B — симулятор вебхука**: отправляет **`POST /api/max/webhook`** с JSON в том же формате, что ожидает **`parse_max_webhook_incoming`** (событие **`message_created`** и т.д.). Ответ бэкенда и код HTTP отображаются под кнопкой. Логика обработки **та же**, что у реального MAX.
- **Панель C — логи сервера**: WebSocket **`WS /api/ws/logs`**; в поток попадают записи **`logging`** из модулей **`src.use_cases.chat`**, **`src.api.routers.max_bot`**, **`src.infrastructure.services.dynamic_llm`** (в т.ч. путь **OpenAILLMService**). Исключения уходят в поток **с полным traceback** (форматирование в **`WebSocketLogHandler`**, **`src/core/logger.py`**).

### Бэкенд

- Роут WebSocket: **`src/api/routers/notifications.py`** — эндпоинт **`/ws/logs`** (итоговый путь **`/api/ws/logs`**).
- Широковещатель: **`src/infrastructure/monitoring/log_ws_broadcaster.py`**.
- Подключение обработчика: **`attach_ws_log_handlers`** из **`src/core/logger.py`** вызывается из **`setup_logging`** (**`src/core/logging.py`**).
- CORS для симулятора: глобально **`allow_origins=["*"]`** в **`src/api/main.py`** — запросы с фронта на **`/api/max/webhook`** разрешены.

### Скрипты фронтенда

- **`frontend/static/js/debug_app.js`** — симулятор и клиент логов (цвета уровней: ERROR — красный, INFO — светлый текст, DEBUG — серый).
- **`frontend/static/js/bots_app.js`** — без изменений логики мониторинга; подключается вместе с **`debug_app.js`** на **`bots.html`**.

---

> **ВНИМАНИЕ (Docker на локальном ПК, рус.):** серверы **MAX не могут вызвать** вебхук по адресу вида `http://localhost:8080` внутри вашей машины. Чтобы реальные события доходили до контейнера, нужен **публичный HTTPS-URL**. Практичный вариант — туннель, например **[ngrok](https://ngrok.com/)**: после `ngrok http 8080` (если снаружи открыт порт **8080** с **Nginx** из **`docker-compose`**) скопируйте выданный **`https://....ngrok-free.app`** и укажите в настройках бота MAX вебхук **`https://....ngrok-free.app/api/max/webhook`**. Без туннеля или без реального домена с доверенным сертификатом входящие вебхуки **не появятся** в логах — используйте **симулятор** на панели «Боты» для проверки пайплайна локально.

---

## SIP и телефония (фаза 10)

### Подключение транка (MCN.ru и аналоги)

1. Закажите у оператора **SIP-транк** (исходящие/входящие), получите **хост регистрара/прокси**, **логин** и **пароль**. Часто для MCN.ru используют хост вида **`sip.mcn.ru`** (уточняйте в личном кабинете).
2. Укажите в **`.env`**: **`SIP_SERVER_IP`**, **`SIP_USER`**, **`SIP_PASSWORD`**, при необходимости **`SIP_OPERATOR_IP`** (IP/CIDR для `identify`; если не задан, подставляется **`SIP_SERVER_IP`**). При старте контейнера **`asterisk`** из шаблона **`pjsip.conf.template`** генерируется **`/etc/asterisk/pjsip.conf`**. Сигналинг и RTP — в **`asterisk`**; приложение **`web`** принимает только **RTP** на выделенных UDP-портах (см. **фаза 11**). Без **`ASTERISK_*`** в приложении остаётся **`StubSIPTelephonyService`** (без реального INVITE из Python).
3. **Входящий**: АТС вызывает **`POST /api/telephony/inbound`** с **`call_id`** и опционально **`caller_phone`**. Ответ содержит **`session_id`** — его нужно использовать при мосте аудио в Redis/ Pipecat (тот же формат истории, что у **`/voice/stream`**).
4. **События**: **`POST /api/telephony/event`** с **`status`**: **`ringing`**, **`answered`**, **`hung_up`**. На **`hung_up`** ставится **`analyze_conversation_task(session_id)`** (если был **`inbound`** и маппинг **`call_id` → session_id** ещё в Redis).
5. **Исходящий автообзвон**: загрузите CSV/XLSX через **`POST /api/dialer/queue/upload`**, затем **`POST /api/dialer/campaign/start`** (или кнопка на **`telephony.html`**). Воркер читает **`pending`** из **`dialer_queue`**, вызывает **`make_outbound_call`**; после реальной интеграции SIP при **ответе абонента** нужно поднять Pipecat с персоной консультанта (**TODO** в коде).

### Переменные окружения (SIP)

| Переменная | Назначение |
|------------|------------|
| **`SIP_SERVER_IP`** | Хост регистратора/прокси SIP (FQDN или IP) |
| **`SIP_OPERATOR_IP`** | IP или CIDR SIP-серверов оператора для `match` в PJSIP identify (если пусто — как **`SIP_SERVER_IP`**) |
| **`SIP_USER`** | Логин учётной записи транка |
| **`SIP_PASSWORD`** | Пароль (не логировать в открытом виде) |

---

## Asterisk и ARI (фаза 11)

### Роль Asterisk

- **Сигналинг SIP** (транк MCN.ru и др.) и **медиа RTP** остаются на **Asterisk**; Python не декодирует тяжёлые кодеки — только лёгкое преобразование **G.711 µ-law ↔ PCM** в **`src/infrastructure/voice/g711.py`**.
- **HTTP/ARI** на порту **8088** (см. **`http.conf`**): REST для команд и **WebSocket** `…/ari/events` для **`StasisStart`** / **`ChannelDestroyed`**.
- **Dialplan** (**`extensions.conf`**): ответ на входящий, затем **`Stasis(voice_ai_app)`** — канал попадает в приложение ARI с тем же именем, что **`ASTERISK_STASIS_APP`**.

### Поток входящего вызова

1. Провайдер шлёт INVITE на **публичный IP VPS:5060/udp** (проброс на контейнер **`asterisk`**).
2. Asterisk поднимает канал **PJSIP**, выполняет **`Answer`** и **`Stasis(voice_ai_app)`**.
3. Процесс **`web`** (lifespan FastAPI) держит **`run_ari_event_listener`**: по **`StasisStart`** для канала **`PJSIP/...`** создаётся **`session_id`**, пишутся ключи Redis (**`analyst_call_meta`**, **`sip_call_map`**), выделяется UDP-порт из диапазона **`ASTERISK_RTP_PORT_MIN`…`MAX`**, слушатель RTP открывает сокет, затем ARI вызывает **`POST /channels/externalMedia`** с **`external_host=web:<порт>`** и форматом **`ulaw`**, создаётся **mixing bridge** и в него добавляются SIP-канал и канал external media.
4. Запускается тот же **`VoicePipelineOrchestrator`**, что и для браузера (**Deepgram → RAG → TTS**), выход TTS уходит обратно в RTP к Asterisk.
5. После завершения сессии вызывается **`analyze_conversation_task(session_id)`** (ОКК), как после WebSocket.

### Настройка MCN.ru на ваш Asterisk

1. В личном кабинете MCN (или у менеджера) укажите **адрес SIP-сервера** — **публичный IP VPS** и порт **5060** (если провайдер принимает только домен — создайте **A-запись** на этот IP).
2. Задайте в **`.env`** переменные **`SIP_SERVER_IP`**, **`SIP_USER`**, **`SIP_PASSWORD`**, при FQDN в **`SIP_SERVER_IP`** обычно нужен отдельный **`SIP_OPERATOR_IP`** (IP из документации MCN для `identify`). Шаблон: **`infrastructure/asterisk/config/pjsip.conf.template`**.
3. Пересоберите и перезапустите **`asterisk`**: `docker compose build asterisk && docker compose up -d asterisk` (или **`restart`** после первой сборки).
4. Проверьте регистрацию/доступность транка командами Asterisk CLI (**`docker compose exec asterisk asterisk -rvvv`**, затем **`pjsip show endpoints`**) — точные команды зависят от образа.

### Файрвол VPS (UDP)

Откройте с хоста (или на облачном security group):

- **5060/udp** — SIP;
- **10000–10500/udp** — RTP (диапазон должен совпадать с **`rtp.conf`** и **`docker-compose.yml`**).

Для **теста без внешнего файрвола** убедитесь, что локальный брандмауэр ОС не режет эти порты. **Порты RTP приложения** (**`18000`…** на сервисе **`web`**) пробрасывать наружу обычно **не нужно**: трафик идёт **между контейнерами** `asterisk` ↔ `web` в одной Docker-сети.

### Переменные окружения (Asterisk / приложение)

| Переменная | Назначение |
|------------|------------|
| **`ASTERISK_URL`** | Базовый URL ARI, например **`http://asterisk:8088/ari`** |
| **`ASTERISK_ARI_USER`** | Логин из **`ari.conf`** (секция **`[voiceai]`** → пользователь **`voiceai`**) |
| **`ASTERISK_ARI_PASSWORD`** | Пароль ARI |
| **`ASTERISK_STASIS_APP`** | Имя Stasis-приложения (**`voice_ai_app`**) |
| **`ASTERISK_RTP_ADVERTISE_HOST`** | Имя хоста/сервиса, куда Asterisk шлёт RTP (**`web`** в Compose) |
| **`ASTERISK_RTP_PORT_MIN`**, **`ASTERISK_RTP_PORT_MAX`** | Пул UDP-портов на контейнере **`web`** (число параллельных вызовов ограничено размером пула) |

### Ограничения и TODO

- Слушатель ARI должен работать **в одном экземпляре** **`web`** (или нужна внешняя координация), иначе два процесса будут получать одни и те же события.
- Исходящий вызов из приложения через ARI (**`Originate`**) — **TODO** в **`AsteriskTelephonyService.make_outbound_call`**.

---

## Bitrix24 и лид из диалога (фаза 7)

1. В **Bitrix24** создайте **входящий вебхук** с правом **`crm`** (достаточно операций с лидами).
2. URL вебхука для вызова **`crm.lead.add`** имеет вид:  
   `https://<ваш-портал>.bitrix24.ru/rest/<user_id>/<код>/crm.lead.add`  
   Укажите его целиком в **`BITRIX24_WEBHOOK_URL`** (см. `.env.example`).
3. Адаптер **`Bitrix24CRMAdapter`** шлёт **POST** с JSON **`fields`**: имя, телефон, комментарий (контекст), источник **WEB**. Ответ REST: **`result`** — числовой **ID** лида в портале.
4. Если переменная **не задана**, подставляется **`NullCRMService`** (лог + фиктивный id); архитектура не ломается.
5. Модель **OpenAI** может вызвать инструмент **`record_lead`**; сценарий **`ProcessTextMessageUseCase`** вызывает **`ICRMService.create_lead`** и добавляет ответ-подтверждение пользователю.

---

## Фоновый аналитик (ОКК) и таблицы БД (фаза 7 + 9)

- Миграция **`002_call_analytics`**: **`call_records`**, **`call_analytics`** (ОКК для диалогов «клиент ↔ ИИ-консультант»).
- Миграция **`003_training`**: **`training_scenarios`**, **`training_sessions`**; в миграции есть **сид** одного сценария по умолчанию (см. файл; **TODO** на вынос сидов — в ревизии).
- Миграция **`004_sip_dialer`**: у **`call_records`** поля **`direction`**, **`remote_phone`**; таблица **`dialer_queue`**.
- Миграция **`005_system_settings`**: таблица **`system_settings`** (ключ, значение, описание, **`updated_at`**) и сиды по умолчанию (**`LLM_PROVIDER=deepseek`**, пустые ключи API, промпты). **# TODO:** шифрование секретов at rest — в комментарии миграции.
- Миграция **`006`**: ключи SaluteSpeech в **`system_settings`**; миграция **`009`**: сид **`MAX_BOT_TOKEN`**; миграция **`010`**: таблица **`chat_messages`** и сид **`MAX_CONTEXT_LIMIT=10`**; миграция **`011`**: **`MAX_USE_POLLING`**; миграция **`012`**: **`TEXT_BOT_SYSTEM_SUPPLEMENT`**.
- Задача **`analyze_conversation_task(session_id)`** (`src/workers/analyst.py`):
  1. Читает историю из **Redis**.
  2. Если в Redis есть ключ **`trainer_session:{session_id}`** (ставится при подключении в режиме тренажёра): сохраняет **`call_records`** со статусом **`training`**, вызывает **`ILLMService.analyze_training_performance`** (промпт **Sales Coach**), пишет **`training_sessions`**; строка **`call_analytics`** **не** создаётся.
  3. Иначе — как раньше: **`call_records`** + **`call_analytics`** (**ОКК**). Поля **`direction`** и **`remote_phone`** подставляются из ключа **`analyst_call_meta:{session_id}`**, если его положил вебхук SIP (**`/api/telephony/inbound`**), иначе по умолчанию **`web`** / пустой номер.
- **Автозапуск**: при закрытии **WebSocket** голоса (`/voice/stream`) или завершении **SIP-сессии через ARI/RTP** в очередь ставится та же задача.
- **Текстовый чат**: после окончания переписки клиент вызывает **`POST /api/chat/finalize`** с **`session_id`**, чтобы не гонять анализ после каждого сообщения.

Проверка вручную:

```bash
set PYTHONPATH=.
alembic upgrade head
celery -A src.core.celery_app worker --loglevel=info
```

В другом терминале (после нескольких **`POST /api/chat/text`** с одним `session_id`). Через Nginx (Compose):

```bash
curl -s -X POST "http://127.0.0.1:8080/api/chat/finalize" -H "Content-Type: application/json" -d "{\"session_id\": \"<uuid-сессии>\"}"
```

Либо напрямую к uvicorn на **8000** (если проброшен порт или локальный запуск):

```bash
curl -s -X POST "http://127.0.0.1:8000/api/chat/finalize" -H "Content-Type: application/json" -d "{\"session_id\": \"<uuid-сессии>\"}"
```

Дождитесь логов воркера и обновите **`http://localhost:8080/`** (таблица подгружается с **`GET /api/calls`**).

---

## Память диалога (Redis)

- Каждый диалог идентифицируется **`session_id`** (UUID). Клиент может не передавать его в первом сообщении — сервер создаст новый UUID и вернёт его в ответе; дальше тот же `session_id` нужно присылать в теле запроса для продолжения беседы.
- История хранится в **Redis**: ключ вида **`chat_session:{session_id}`**, значение — **список** (LPUSH/RPUSH через `RPUSH` + `LRANGE`), элементы — **JSON**-строки `{"role":"user"|"assistant","content":"..."}`.
- На ключ выставляется **TTL** (по умолчанию **24 часа**, переменная **`CHAT_MEMORY_TTL_SECONDS`**), чтобы старые сессии не копились в RAM на VPS.
- Порт **`IChatMemoryRepository`** реализован классом **`RedisChatMemoryRepository`** в `src/infrastructure/repositories.py`; сценарий **`ProcessTextMessageUseCase`** не знает про Redis.

## Пайплайн `POST /api/chat/text` (RAG + память + CRM)

1. Загрузка **истории** из Redis по `session_id`.
2. **Эмбеддинг** текущего `message` → **векторный поиск** (до 3 фрагментов) в pgvector.
3. Цикл **OpenAI tool calling**: **`ILLMService.generate_sales_response_with_tools`** с инструментом **`record_lead`**; при вызове — **`ICRMService.create_lead`**, результат возвращается модели в сообщениях **`role: tool`** до финального текста.
4. Сохранение в Redis **реплики пользователя** и **итогового ответа ассистента**.

## Celery (фоновые задачи)

- Приложение: **`src/core/celery_app.py`**, команда **`celery -A src.core.celery_app worker`**.
- **Брокер** и **backend** — Redis (**`CELERY_BROKER_URL`**, **`CELERY_RESULT_BACKEND`**); чат — **`REDIS_URI`** (БД **0**).
- **`analyze_conversation_task`**: реализация в **`src/workers/analyst.py`**, регистрация в **`src/workers/tasks.py`**; использует **`AsyncSessionLocal`**, **`PostgresSettingsRepository`** + **`DynamicLLMService`**, Redis и **`Settings`**.
- Воркеру нужны **`POSTGRES_URI`**, **`REDIS_URI`**, **`OPENAI_API_KEY`** (для ОКК и тренера).

```bash
set PYTHONPATH=.
celery -A src.core.celery_app worker --loglevel=info
```

```python
from src.workers.tasks import analyze_conversation_task
analyze_conversation_task.delay("session-uuid-here")
```

## Архитектура (Clean Architecture)

| Каталог / файл | Назначение |
|----------------|------------|
| `src/use_cases/interfaces.py` | Порты: **`ILLMService`**, **`ITelephonyService`**, **`IDialerQueueRepository`**, др. |
| `src/use_cases/chat.py` | **`ProcessTextMessageUseCase`**: опциональный **`system_prompt_override`**, **`skip_rag`**, отключение CRM-tools |
| `src/infrastructure/repositories.py` | **`SqlAlchemyTrainingScenarioRepository`**, **`SqlAlchemyTrainingSessionRepository`**, др. |
| `src/infrastructure/services/` | **`dynamic_llm.DynamicLLMService`**, **`openai_embedding`**, **`bitrix24`** |
| `src/infrastructure/training_session_redis.py` | Ключ **`trainer_session:`** для воркера |
| `src/infrastructure/sip_call_redis.py` | **`analyst_call_meta:`**, маппинг **`sip_call:`** для ОКК после SIP |
| `src/infrastructure/voice/sip_pipecat_adapter.py` | **`SIPPipecatAdapter`**, **`StubSIPTelephonyService`** |
| `src/workers/dialer.py` | **`run_outbound_campaign_sync`** |
| `src/core/celery_app.py` | Фабрика Celery |
| `src/workers/tasks.py` | Регистрация **`analyze_conversation_task`** |
| `src/workers/analyst.py` | ОКК или оценка тренажёра (async + **`analyze_conversation_sync`**) |
| `src/api/dependencies.py` | Репозиторий сценариев, CRM, звонки, чат |
| `src/api/main.py` | **lifespan**, **CORS**, роутеры **`/api`**, **`/voice`** |
| `src/infrastructure/voice/` | **`VoicePipelineOrchestrator`**: параметры **`voice_mode`**, **`training_scenario`** |
| `src/api/routers/voice.py` | **`/voice/stream`**, query **`mode`**, **`scenario_id`**, Redis-мета |
| `src/api/routers/training.py` | **`GET`/`POST /api/scenarios`** |
| `src/api/routers/telephony.py` | **`/api/telephony/inbound`**, **`/api/telephony/event`** |
| `src/api/routers/dialer.py` | **`/api/dialer/queue/upload`**, **`/api/dialer/campaign/start`** |
| `src/api/routers/calls.py` | **`GET /api/calls`** |
| `frontend/` | **`telephony.html`**, **`scenarios.html`**, **`tester.html`**, Nginx |

## Требования

- Python **3.10–3.12** (рекомендуется для **`pipecat-ai==0.0.60`**: на **3.13** под Windows часто нет готового колеса **numpy 1.26.x**, сборка из исходников требует MSVC; проще **conda install numpy** или снизить версию Python). Docker Compose (Postgres pgvector, Redis).
- Для реальных ответов LLM — **`OPENAI_API_KEY`**
- Для голоса — **`DEEPGRAM_API_KEY`**; для TTS по умолчанию снова **OpenAI** (или **ElevenLabs**, см. таблицу)

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `APP_ENV`, `APP_DEBUG` | Окружение и отладка |
| `POSTGRES_URI` | Async SQLAlchemy |
| **`REDIS_URI`** | Redis **БД 0** — память диалогов |
| **`CELERY_BROKER_URL`** | Redis для брокера Celery (рекомендуется **/1**) |
| **`CELERY_RESULT_BACKEND`** | Redis для результатов задач (рекомендуется **/2**) |
| **`CHAT_MEMORY_TTL_SECONDS`** | TTL ключа сессии в секундах (по умолчанию **86400**) |
| `OPENAI_API_KEY` | Опционально; **резерв** для эмбеддингов RAG, если в БД пустой **`OPENAI_API_KEY`**; основной ключ LLM задаётся в панели **«Настройки»** |
| **`DEEPGRAM_API_KEY`** | Облачный STT для **`/voice/stream`** (пока только из env) |
| **`VOICE_TTS_PROVIDER`** | **`openai`** (по умолчанию) или **`elevenlabs`** |
| **`OPENAI_TTS_VOICE`**, **`OPENAI_TTS_MODEL`** | Голос и модель OpenAI TTS |
| **`ELEVENLABS_API_KEY`**, **`ELEVENLABS_VOICE_ID`** | Нужны при **`VOICE_TTS_PROVIDER=elevenlabs`** |
| **`VOICE_STT_LANGUAGE`** | Код языка Deepgram (например **`ru`**) |
| **`BITRIX24_WEBHOOK_URL`** | Полный URL вебхука **`crm.lead.add`** (опционально) |
| **`SIP_SERVER_IP`**, **`SIP_USER`**, **`SIP_PASSWORD`** | Учётные данные SIP-транка (MCN.ru и др.; см. раздел «SIP и телефония») |
| **`ASTERISK_URL`**, **`ASTERISK_ARI_USER`**, **`ASTERISK_ARI_PASSWORD`** и др. | ARI + RTP (см. «Asterisk и ARI») |

## Запуск через Docker Compose

```bash
docker compose build
docker compose up
```

Сервисы: **`web`**, **`frontend`**, **`postgres`**, **`redis`**, **`celery_worker`**, **`asterisk`** (SIP **5060/udp**, ARI **8088/tcp**, RTP **10000–10500/udp**). Панель: **`http://localhost:8080`**. После старта при необходимости выполните **`alembic upgrade head`** в контейнере `web`.

## Эндпоинт `POST /api/chat/text`

Тело JSON:

- **`message`** (обязательно)
- **`session_id`** (опционально, UUID) — для продолжения диалога

Ответ: **`reply`**, **`session_id`**.

```bash
curl -s -X POST "http://127.0.0.1:8080/api/chat/text" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Напомни цену на станок из прошлого сообщения\"}"
```

С повторным использованием сессии:

```bash
curl -s -X POST "http://127.0.0.1:8080/api/chat/text" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Уточни срок поставки\", \"session_id\": \"00000000-0000-0000-0000-000000000000\"}"
```

(Подставьте реальный UUID из предыдущего ответа.)

## Прочие эндпоинты (префикс `/api` у HTTP)

- **`POST /api/leads`** — создание лида (фаза 2)
- **`POST /api/chat/finalize`** — завершить текстовую сессию и поставить задачу ОКК в Celery
- **`GET /api/health`** — проверка API
- **`GET /api/calls`** — список **`call_records`** с вложенной **`analytics`** (для дашборда)
- **`GET /api/scenarios`**, **`POST /api/scenarios`** — сценарии тренажёра (JSON)
- **`POST /api/telephony/inbound`**, **`POST /api/telephony/event`** — вебхуки АТС (SIP)
- **`POST /api/dialer/queue/upload`** (multipart **`file`**) — загрузка номеров в **`dialer_queue`**
- **`POST /api/dialer/campaign/start`** — постановка **`run_outbound_campaign_task`** в Celery
- **`GET /api/settings`**, **`PUT /api/settings`** — динамические параметры (ключи API маскируются в ответе)
- **`WebSocket /voice/stream`** — голос (браузер, Protobuf); по закрытию сокета — **`analyze_conversation_task`**
- **SIP через Asterisk** — без отдельного WS: ARI + **UDP RTP** к приложению (см. «Asterisk и ARI»); по завершении сессии — тот же **`analyze_conversation_task`**

## Локальный запуск (без Docker)

```bash
pip install -r requirements.txt
set PYTHONPATH=.
alembic upgrade head
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

Отдельно: Redis и (при необходимости) второй терминал с **Celery worker** (см. выше). Запросы к API с фронта: **`http://127.0.0.1:8000/api/...`** (CORS уже разрешает `*`). Либо поднимите только Nginx из **`frontend/`** и укажите в конфиге **`proxy_pass`** на **`127.0.0.1:8000`**.

## Динамические настройки (фаза 12)

- **Таблица** **`system_settings`**: первичный ключ **`key`** (строка), **`value`** (TEXT), **`description`**, **`updated_at`**.
- **Кэш Redis**: при **`get_value`** сначала читается Redis; при промахе — PostgreSQL, затем запись в кэш. При **`PUT /api/settings`** соответствующие ключи кэша **удаляются**.
- **Провайдер LLM**: **`LLM_PROVIDER`** = **`deepseek`** (по умолчанию) или **`openai`**. Клиент — **`AsyncOpenAI`**; для DeepSeek задаётся **`base_url=https://api.deepseek.com`**.
- **Эмбеддинги RAG** остаются на API OpenAI (**`text-embedding-3-small`**); ключ **`OPENAI_API_KEY`** берётся из настроек БД, при пустом значении — из переменной окружения **`OPENAI_API_KEY`** (удобно до первой настройки панели).
- Панель: **`http://localhost:8080/settings.html`** (после **`alembic upgrade head`** и **`docker compose up`**).

## Структура (фаза 12)

```
infrastructure/asterisk/config/   # Asterisk (фаза 11)
frontend/        # settings.html, telephony.html, scenarios.html, tester.html, static/
src/
  api/routers/settings.py
  domain/          # system_setting_keys.py, default_system_prompts.py, SystemSetting
  infrastructure/  # models SystemSettingModel, PostgresSettingsRepository, dynamic_llm.py
  workers/
  ...
```

## Дальнейшие фазы

Шифрование секретов в БД, **Originate** (ARI), отчёт по **`training_sessions`** в UI, авторизация **`/api/settings`**, мониторинг Celery.
