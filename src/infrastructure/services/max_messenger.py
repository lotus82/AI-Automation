"""HTTP-клиент к Bot API мессенджера MAX (VK): только httpx, без сторонних обёрток.

Long polling GET ``/updates`` на ``platform-api.max.ru`` — транспортный слой; сценарий ответа тот же, что у POST ``/api/max/webhook``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import socket
from collections import Counter
from typing import Any
from uuid import UUID

import httpx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.domain import system_setting_keys as sk
from src.infrastructure.services.max_incoming_group import (
    apply_max_group_mention_rules,
    detect_max_group_chat,
)
from src.use_cases.chat import ProcessTextMessageUseCase
from src.use_cases.interfaces import ISettingsRepository

# Устаревший хост (раньше предполагался путь ``/bot<token>/sendMessage``); отправка идёт через **platform-api**.
_DEFAULT_MAX_API_BASE = "https://api.max.ru"
# Platform API: GET ``/updates``, POST ``/messages`` — заголовок ``Authorization: <токен>``.
_DEFAULT_MAX_PLATFORM_API_BASE = "https://platform-api.max.ru"

logger = logging.getLogger(__name__)

_POLL_LIMIT = 100
_POLL_LONG_TIMEOUT_SEC = 30
_POLL_TYPES = (
    "message_created",
    "message_callback",
    "bot_started",
    "BOT_STARTED",
    "voice_call_incoming",
    "VOICE_CALL_INCOMING",
    "call_incoming",
    "CALL_INCOMING",
)

# Лимит текста в POST /messages: платформа MAX считает **байты UTF-8** (часто ≤4096), не «символы».
# Обрезка [:4000] по символам для кириллицы даёт >8000 байт → 400 Bad Request.
_MAX_OUTGOING_MESSAGE_UTF8_BYTES = 3800
# MAX CDN для type=audio: сжатый поток; синтез SaluteSpeech REST — Opus в OGG (не WAV).
_MAX_VOICE_UPLOAD_FILENAME = "voice.ogg"
_MAX_VOICE_UPLOAD_MIME = "audio/ogg"


def _max_cdn_attachment_token(body: Any) -> str | None:
    """Идентификатор вложения из JSON CDN: ``fileId`` / ``file_id`` или ``token`` (в ``/messages`` для audio всё равно поле ``payload.token``)."""
    if not isinstance(body, dict):
        return None
    for key in ("fileId", "file_id", "token"):
        v = body.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _truncate_utf8_for_max_api(text: str, max_bytes: int = _MAX_OUTGOING_MESSAGE_UTF8_BYTES) -> str:
    """Укладывает текст в лимит байт UTF-8, не ломая суррогаты и многобайтовые символы."""
    s = (text or "").strip()
    if not s:
        return ""
    raw = s.encode("utf-8")
    if len(raw) <= max_bytes:
        return s
    suffix = "…"
    suf_b = suffix.encode("utf-8")
    budget = max_bytes - len(suf_b)
    if budget <= 0:
        return suffix if max_bytes >= len(suf_b) else raw[:max_bytes].decode("utf-8", errors="ignore")
    cut = budget
    while cut > 0:
        try:
            return raw[:cut].decode("utf-8") + suffix
        except UnicodeDecodeError:
            cut -= 1
    return suffix


async def _post_max_voice_multipart(
    client: httpx.AsyncClient,
    upload_url: str,
    audio_data: bytes,
) -> httpx.Response:
    """POST **multipart/form-data** на URL из ``/uploads``: поле **file**, **.ogg** + **audio/ogg** (Opus из REST SaluteSpeech)."""
    # Ключ ``file`` + кортеж с именем даёт ``filename=`` в Content-Disposition; общий Content-Type не задаём — httpx выставляет boundary.
    files = {
        "file": (_MAX_VOICE_UPLOAD_FILENAME, audio_data, _MAX_VOICE_UPLOAD_MIME),
    }
    return await client.post(upload_url, files=files)


def _max_instance_tag() -> str:
    """Идентификатор процесса для логов (дублирование long poll по токену)."""
    try:
        host = socket.gethostname()
    except OSError:
        host = "?"
    return f"{host}/{os.getpid()}"


def _max_token_suffix(token: str) -> str:
    """Хвост токена без раскрытия полного значения."""
    t = (token or "").strip()
    if not t:
        return "(empty)"
    if len(t) <= 4:
        return "****"
    return f"...{t[-4:]}"


def _max_poll_marker_storage_key(token: str) -> str:
    """Ключ Redis для cursor long poll (один токен — одна очередь updates на стороне MAX)."""
    t = (token or "").strip().encode("utf-8")
    digest = hashlib.sha256(t).hexdigest()[:24]
    return f"max:long_poll:marker:{digest}"


def _max_updates_type_counts(updates: list[Any]) -> str:
    c: Counter[str] = Counter()
    for u in updates:
        if isinstance(u, dict):
            k = (u.get("update_type") or "?").strip() or "?"
            c[k] += 1
        else:
            c["<not dict>"] += 1
    return ",".join(f"{k}:{v}" for k, v in sorted(c.items()))


def _max_markup_mention_snippets(body: dict[str, Any]) -> str:
    """Добавляет к поиску @username из ``markup`` (иногда клиент не дублирует их в ``body.text``)."""
    markup = body.get("markup") or body.get("markups")
    if not isinstance(markup, list):
        return ""
    parts: list[str] = []
    for m in markup:
        if not isinstance(m, dict):
            continue
        mt = str(m.get("type") or "").lower()
        if mt in ("user", "mention", "markupuser"):
            un = m.get("username") or m.get("user_name") or m.get("name")
            if un and str(un).strip():
                parts.append("@" + str(un).strip().lstrip("@"))
    return " ".join(parts).strip()


def extract_max_sender_display_name(sender: Any, *, _depth: int = 0) -> str | None:
    """Извлекает имя (или ник) отправителя из объекта ``sender`` / ``user`` в payload MAX.

    Пробуем поля в порядке от наиболее «человеческого» отображения к запасным вариантам API.
    Если данных нет — ``None`` (как и пустая строка после ``strip``).
    """
    if _depth > 4:
        return None
    if not isinstance(sender, dict):
        return None
    if sender.get("is_bot") is True:
        return None
    name = (sender.get("name") or "").strip()
    if name:
        return name
    sender_name = (sender.get("sender_name") or "").strip()
    if sender_name:
        return sender_name
    first = (sender.get("first_name") or "").strip()
    last = (sender.get("last_name") or "").strip()
    if first and last:
        return f"{first} {last}".strip()
    if first:
        return first
    user_block = sender.get("user")
    if isinstance(user_block, dict):
        nested = extract_max_sender_display_name(user_block, _depth=_depth + 1)
        if nested:
            return nested
    username = (sender.get("username") or "").strip()
    if username:
        return username.lstrip("@")
    return None


def _max_effective_message_text(body: dict[str, Any]) -> str:
    """Плоский текст + упоминания из разметки (для фильтра группы и RAG)."""
    raw = (body.get("text") or "").strip()
    extra = _max_markup_mention_snippets(body)
    if raw and extra:
        return f"{raw} {extra}".strip()
    return raw or extra


def _max_parse_skip_reason(raw: dict[str, Any]) -> str | None:
    """Краткая причина, почему ``parse_max_webhook_incoming`` вернёт ``None`` (для DEBUG)."""
    ut = (raw.get("update_type") or "").strip()
    if ut == "message_callback":
        msg = raw.get("message")
        if not isinstance(msg, dict):
            return "message_callback: нет message"
        if not isinstance(msg.get("recipient"), dict):
            return "message_callback: нет recipient"
        cb = raw.get("callback")
        if not isinstance(cb, dict):
            return "message_callback: нет callback"
        if not (cb.get("payload") or "").strip():
            return "message_callback: пустой callback.payload"
        if msg.get("recipient", {}).get("chat_id") is None:
            return "message_callback: нет chat_id"
        return "message_callback: другое (см. parse_max_webhook_incoming)"

    if ut != "message_created":
        return f"update_type={ut or '(пусто)'}"

    msg = raw.get("message")
    if not isinstance(msg, dict):
        return "message_created: нет message"
    sender = msg.get("sender")
    if isinstance(sender, dict) and sender.get("is_bot") is True:
        return "message_created: is_bot=true"
    if not isinstance(msg.get("recipient"), dict):
        return "message_created: нет recipient"
    if msg.get("recipient", {}).get("chat_id") is None:
        return "message_created: нет chat_id"
    body = msg.get("body")
    if not isinstance(body, dict):
        return "message_created: нет body"
    if not _max_effective_message_text(body):
        return "message_created: пустой text и markup без username"
    return "message_created: другое"


def parse_max_webhook_incoming(
    payload: dict[str, Any],
) -> tuple[int, str, str | None, bool] | None:
    """Извлекает ``chat_id``, текст, подпись пользователя и признак **группового** чата.

    Поддерживаются события **message_created** (текст в ``message.body.text``)
    и **message_callback** (нажатие кнопки: текст берётся из ``callback.payload``).
    Сообщения от бота (**sender.is_bot**) игнорируются.
    """
    update_type = (payload.get("update_type") or "").strip()

    if update_type == "message_created":
        msg = payload.get("message")
        if not isinstance(msg, dict):
            return None
        sender = msg.get("sender")
        if isinstance(sender, dict) and sender.get("is_bot") is True:
            return None
        recipient = msg.get("recipient")
        if not isinstance(recipient, dict):
            return None
        chat_id = recipient.get("chat_id")
        if chat_id is None:
            return None
        body = msg.get("body")
        if not isinstance(body, dict):
            return None
        text = _max_effective_message_text(body)
        if not text:
            return None
        user_info = extract_max_sender_display_name(sender) if isinstance(sender, dict) else None
        cid = int(chat_id)
        is_group = detect_max_group_chat(
            chat_id=cid,
            recipient=recipient,
            sender=sender if isinstance(sender, dict) else None,
        )
        return cid, text, user_info, is_group

    if update_type == "message_callback":
        msg = payload.get("message")
        if not isinstance(msg, dict):
            return None
        recipient = msg.get("recipient")
        if not isinstance(recipient, dict):
            return None
        chat_id = recipient.get("chat_id")
        callback = payload.get("callback")
        if not isinstance(callback, dict):
            return None
        payload_str = (callback.get("payload") or "").strip()
        if chat_id is None or not payload_str:
            return None
        cb_user = callback.get("user")
        user_info = extract_max_sender_display_name(cb_user) if isinstance(cb_user, dict) else None
        cid = int(chat_id)
        is_group = detect_max_group_chat(
            chat_id=cid,
            recipient=recipient,
            sender=cb_user if isinstance(cb_user, dict) else None,
        )
        return cid, payload_str, user_info, is_group

    return None


_VOICE_CALL_UPDATE_TYPES = frozenset(
    {
        "voice_call_incoming",
        "VOICE_CALL_INCOMING",
        "call_incoming",
        "CALL_INCOMING",
        "incoming_call",
        "INCOMING_CALL",
    }
)


def parse_max_voice_call_incoming(payload: dict[str, Any]) -> tuple[str, str | None] | None:
    """Распознаёт событие входящего VoIP-звонка MAX и извлекает ``call_id`` и имя абонента.

    Возвращает ``(call_id, user_display_name | None)`` или ``None``, если это не звонок или нет id.

    # TODO (рус.): Сверить ``update_type`` и вложенные поля с официальным webhook/long poll MAX.
    """
    ut_raw = (payload.get("update_type") or "").strip()
    ut_lower = ut_raw.lower()
    if ut_raw not in _VOICE_CALL_UPDATE_TYPES:
        if (
            "voice_call" not in ut_lower
            and "call_incoming" not in ut_lower
            and "incoming_call" != ut_lower
        ):
            return None

    call_id: str | None = None
    call_block = payload.get("call") or payload.get("voice_call") or payload.get("voiceCall")
    if isinstance(call_block, dict):
        cid = call_block.get("call_id") or call_block.get("id") or call_block.get("callId")
        if cid is not None and str(cid).strip():
            call_id = str(cid).strip()
    if not call_id:
        for key in ("call_id", "callId", "voice_call_id"):
            v = payload.get(key)
            if v is not None and str(v).strip():
                call_id = str(v).strip()
                break
    if not call_id:
        return None

    user_name: str | None = None
    user_block = payload.get("user") or payload.get("sender") or payload.get("caller")
    if isinstance(user_block, dict):
        user_name = extract_max_sender_display_name(user_block)

    return call_id, user_name


class MaxMessengerClient:
    """Отправка исходящих сообщений; токен: **БД** (панель), иначе fallback из **.env** ``MAX_BOT_TOKEN``."""

    def __init__(
        self,
        *,
        settings_repository: ISettingsRepository,
        api_base_url: str = _DEFAULT_MAX_API_BASE,
        platform_api_base_url: str = _DEFAULT_MAX_PLATFORM_API_BASE,
        env_fallback_max_bot_token: str | None = None,
    ) -> None:
        self._settings_repo = settings_repository
        self._api_base = (api_base_url or _DEFAULT_MAX_API_BASE).rstrip("/")
        self._platform_api_base = (platform_api_base_url or _DEFAULT_MAX_PLATFORM_API_BASE).rstrip("/")
        self._env_fallback_token = (env_fallback_max_bot_token or "").strip() or None

    async def _resolve_bot_token(self) -> str:
        """Сначала ``system_settings``, затем переменная окружения ``MAX_BOT_TOKEN``."""
        db = (await self._settings_repo.get_value(sk.MAX_BOT_TOKEN) or "").strip()
        if db:
            return db
        return (self._env_fallback_token or "").strip()

    async def resolve_bot_token(self) -> str:
        """Публичный доступ к токену (уведомления заказа витрины и т.п.)."""
        return await self._resolve_bot_token()

    async def _db_allows_long_polling(self) -> bool:
        """Читает **MAX_USE_POLLING** из БД (и Redis-кэш репозитория)."""
        raw = await self._settings_repo.get_value(sk.MAX_USE_POLLING)
        if raw is None or not str(raw).strip():
            return True
        low = str(raw).strip().lower()
        return low not in ("0", "false", "no", "off")

    async def answer_call(self, call_id: str) -> None:
        """Принять входящий вызов: команда ``accept`` к Platform API после задержки ``MAX_CALL_ANSWER_DELAY``.

        # TODO (рус.): Уточнить точный путь (например ``/v1/...``) и тело запроса в документации MAX.
        """
        token = await self._resolve_bot_token()
        if not token:
            raise ValueError(
                "MAX_BOT_TOKEN не задан: укажите в панели «Настройки» или в переменной окружения MAX_BOT_TOKEN (.env)"
            )
        cid = (call_id or "").strip()
        if not cid:
            raise ValueError("call_id пустой")

        url = f"{self._platform_api_base}/calls/{cid}/accept"
        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, headers=headers, json={})
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "MAX answer_call: HTTP %s call_id=%s URL=%s ответ: %s",
                    exc.response.status_code,
                    cid,
                    url,
                    (exc.response.text or "")[:800],
                )
                raise
        logger.info("MAX answer_call: вызов принят call_id=%s", cid)

    async def start_polling(
        self,
        use_case: ProcessTextMessageUseCase,
        *,
        session: AsyncSession,
        stop_event: asyncio.Event,
        redis: Redis,
        app_settings: Settings,
        organization_id: UUID | None = None,
    ) -> None:
        """Бесконечный long poll ``GET /updates``; для каждого события — ``use_case.execute`` + ``send_message``.

        Один цикл жизни **AsyncSession** на процесс (см. ``lifespan``): после каждой успешной пары реплик — ``commit``.
        ``organization_id`` — контекст для входящего VoIP (``run_max_inbound_call_background``); текстовые события уже
        используют ``use_case`` с тем же scope.
        """
        # TODO (рус.): Если пользователь захочет использовать официальную JS-библиотеку MAX, потребуется вынести этот поллинг в отдельный Node.js микросервис, который будет проксировать запросы на локальный FastAPI вебхук.
        marker: int | None = None
        marker_context_token: str | None = None
        http_timeout = httpx.Timeout(
            connect=15.0,
            read=float(_POLL_LONG_TIMEOUT_SEC) + 20.0,
            write=15.0,
            pool=15.0,
        )
        url = f"{self._platform_api_base}/updates"
        instance_tag = _max_instance_tag()
        empty_streak = 0
        poll_start_logged = False
        no_token_rounds = 0

        while not stop_event.is_set():
            try:
                if not await self._db_allows_long_polling():
                    await asyncio.sleep(5)
                    continue

                token = await self._resolve_bot_token()
                if not token:
                    no_token_rounds += 1
                    if no_token_rounds in (1, 3, 10) or (no_token_rounds % 30 == 0):
                        logger.warning(
                            "MAX long poll: нет MAX_BOT_TOKEN (БД/панель или .env), опрос невозможен "
                            "(раунд %s, instance=%s)",
                            no_token_rounds,
                            instance_tag,
                        )
                    await asyncio.sleep(10)
                    continue
                no_token_rounds = 0

                if token != marker_context_token:
                    marker = None
                    rkey = _max_poll_marker_storage_key(token)
                    try:
                        raw_marker = await redis.get(rkey)
                        if raw_marker is not None and str(raw_marker).strip():
                            marker = int(str(raw_marker).strip())
                            logger.info(
                                "MAX long poll: marker восстановлен из Redis (смещение очереди updates), "
                                "instance=%s …%s value=%s",
                                instance_tag,
                                rkey[-14:],
                                marker,
                            )
                    except (TypeError, ValueError) as exc:
                        logger.warning(
                            "MAX long poll: некорректный marker в Redis key=…%s: %s",
                            rkey[-14:],
                            exc,
                        )
                        marker = None
                    except Exception as exc:
                        logger.warning("MAX long poll: чтение marker из Redis: %s", exc)
                        marker = None
                    if marker is None:
                        boot = (os.environ.get("MAX_POLL_MARKER_BOOTSTRAP") or "").strip()
                        if boot:
                            try:
                                marker = int(boot)
                                logger.info(
                                    "MAX long poll: стартовый marker из MAX_POLL_MARKER_BOOTSTRAP=%s "
                                    "(уберите из .env после первого успешного опроса)",
                                    marker,
                                )
                            except (TypeError, ValueError):
                                logger.warning(
                                    "MAX long poll: MAX_POLL_MARKER_BOOTSTRAP не число: %r",
                                    boot[:32],
                                )
                    marker_context_token = token

                if not poll_start_logged:
                    logger.info(
                        "MAX long poll: старт worker instance=%s platform_api=%s token_suffix=%s "
                        "(дубликат токена в другом процессе забирает updates; с вебхуком long poll не совмещают)",
                        instance_tag,
                        self._platform_api_base,
                        _max_token_suffix(token),
                    )
                    poll_start_logged = True

                params: list[tuple[str, str]] = [
                    ("limit", str(_POLL_LIMIT)),
                    ("timeout", str(_POLL_LONG_TIMEOUT_SEC)),
                ]
                for t in _POLL_TYPES:
                    params.append(("types", t))
                if marker is not None:
                    params.append(("marker", str(marker)))

                async with httpx.AsyncClient(timeout=http_timeout) as client:
                    response = await client.get(
                        url,
                        headers={"Authorization": token},
                        params=params,
                    )
                    response.raise_for_status()
                    try:
                        body = response.json()
                    except ValueError:
                        logger.warning("MAX long poll: тело ответа не является JSON")
                        await asyncio.sleep(5)
                        continue

            except asyncio.CancelledError:
                raise
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "MAX long poll: HTTP %s — %s",
                    exc.response.status_code,
                    (exc.response.text or "")[:500],
                )
                await asyncio.sleep(5)
                continue
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                logger.warning("MAX long poll: сеть/таймаут — %s", exc)
                await asyncio.sleep(5)
                continue
            except Exception:
                logger.exception("MAX long poll: непредвиденная ошибка")
                await asyncio.sleep(5)
                continue

            if not isinstance(body, dict):
                await asyncio.sleep(2)
                continue

            updates_raw = body.get("updates")
            updates_list = updates_raw if isinstance(updates_raw, list) else []
            n_updates = len(updates_list)
            prev_marker = marker
            new_marker_raw = body.get("marker")

            m_raw = body.get("marker")
            if m_raw is not None:
                try:
                    marker = int(m_raw)
                    if token:
                        try:
                            await redis.set(
                                _max_poll_marker_storage_key(token),
                                str(marker),
                            )
                        except Exception as exc:
                            logger.warning("MAX long poll: запись marker в Redis: %s", exc)
                except (TypeError, ValueError):
                    pass

            if n_updates == 0:
                empty_streak += 1
                if empty_streak in (1, 3, 10) or (empty_streak % 20 == 0):
                    logger.warning(
                        "MAX long poll: пустая очередь updates (%s раз подряд) marker %s→%s "
                        "instance=%s token_suffix=%s — если в чате пишут, а здесь пусто: отключите вебхук "
                        "в кабинете MAX (один способ доставки); проверьте второй Docker/хост с тем же токеном; "
                        "совпадение токена в БД и .env.",
                        empty_streak,
                        prev_marker,
                        new_marker_raw,
                        instance_tag,
                        _max_token_suffix(token),
                    )
            else:
                empty_streak = 0
                logger.info(
                    "MAX long poll: пакет updates=%s types=[%s] marker %s→%s instance=%s token_suffix=%s",
                    n_updates,
                    _max_updates_type_counts(updates_list),
                    prev_marker,
                    new_marker_raw,
                    instance_tag,
                    _max_token_suffix(token),
                )

            accepted_by_parser = 0
            replies_sent = 0
            for raw_update in updates_list:
                if stop_event.is_set():
                    break
                if not isinstance(raw_update, dict):
                    continue
                parsed_call = parse_max_voice_call_incoming(raw_update)
                if parsed_call is not None:
                    call_id_v, user_label_v = parsed_call

                    async def _voip_bg(
                        c_id: str,
                        u_lab: str | None,
                        oid: UUID | None,
                    ) -> None:
                        from src.infrastructure.voice.max_call_session import (
                            run_max_inbound_call_background,
                        )

                        await run_max_inbound_call_background(
                            call_id=c_id,
                            user_label=u_lab,
                            redis=redis,
                            settings=app_settings,
                            organization_id=oid,
                        )

                    asyncio.create_task(_voip_bg(call_id_v, user_label_v, organization_id))
                    logger.info(
                        "MAX long poll: запланирована обработка VoIP call_id=%s instance=%s",
                        call_id_v,
                        instance_tag,
                    )
                    continue
                try:
                    from src.infrastructure.mis_max_bot_patient_reg_flow import (
                        try_max_bot_mis_patient_registration_flow,
                    )

                    mis_reg = await try_max_bot_mis_patient_registration_flow(
                        raw_update,
                        session=session,
                        redis=redis,
                        settings=app_settings,
                        query_organization_id=organization_id,
                    )
                except Exception:
                    await session.rollback()
                    logger.exception("MAX long poll: сбой регистрации МИС (вебхук-совместимый сценарий)")
                    continue
                if mis_reg is not None:
                    try:
                        await session.commit()
                    except Exception:
                        await session.rollback()
                    continue
                parsed = parse_max_webhook_incoming(raw_update)
                if parsed is None:
                    if logger.isEnabledFor(logging.DEBUG):
                        rs = _max_parse_skip_reason(raw_update)
                        if rs:
                            logger.debug("MAX long poll: не разобрано: %s", rs)
                    continue
                accepted_by_parser += 1
                chat_id, user_text, user_label, is_group = parsed
                processed = await apply_max_group_mention_rules(
                    self._settings_repo,
                    raw_user_text=user_text,
                    is_group_chat=is_group,
                )
                if processed is None:
                    logger.info(
                        "MAX long poll: пропуск (группа без упоминания бота или пустой текст), chat_id=%s",
                        chat_id,
                    )
                    continue
                session_id = str(chat_id)

                async def on_intermediate(msg: str) -> None:
                    await self.send_message(chat_id, msg)

                voice_audio: list[bytes] = []

                async def on_voice_generated(data: bytes) -> None:
                    voice_audio.append(data)

                try:
                    reply = await use_case.execute(
                        processed,
                        session_id,
                        interaction_user_label=user_label,
                        user_name=user_label,
                        append_text_messenger_system_supplement=True,
                        on_intermediate_message=on_intermediate,
                        on_voice_generated=on_voice_generated,
                    )
                except Exception:
                    await session.rollback()
                    logger.exception("Сбой сценария текста MAX (long poll), chat_id=%s", chat_id)
                    await asyncio.sleep(5)
                    continue

                try:
                    await session.commit()
                except Exception:
                    await session.rollback()
                    logger.exception("Сбой commit после ответа LLM (long poll), chat_id=%s", chat_id)
                    await asyncio.sleep(5)
                    continue

                try:
                    await self.send_message(chat_id, reply)
                    replies_sent += 1
                    logger.info(
                        "MAX long poll: ответ отправлен chat_id=%s len(reply)=%s instance=%s",
                        chat_id,
                        len(reply or ""),
                        instance_tag,
                    )
                    if voice_audio:
                        try:
                            await self.send_voice_message(chat_id, voice_audio[0])
                        except Exception:
                            logger.exception(
                                "MAX long poll: не удалось отправить голосовое вложение, chat_id=%s",
                                chat_id,
                            )
                except httpx.HTTPStatusError as exc:
                    logger.error(
                        "MAX long poll: сообщение не доставлено HTTP %s chat_id=%s тело ответа API: %s",
                        exc.response.status_code,
                        chat_id,
                        (exc.response.text or "")[:800],
                    )
                except Exception:
                    logger.exception("Сбой send_message MAX (long poll), chat_id=%s", chat_id)

            if n_updates > 0:
                logger.info(
                    "MAX long poll: итог пакета updates=%s принято_парсером=%s отправлено_ответов=%s",
                    n_updates,
                    accepted_by_parser,
                    replies_sent,
                )

    async def send_message(self, chat_id: int, text: str) -> None:
        """POST ``/messages`` на Platform API: ``chat_id`` в query, токен в ``Authorization`` (см. dev.max.ru)."""
        token = await self._resolve_bot_token()
        if not token:
            msg = (
                "MAX_BOT_TOKEN не задан: укажите в панели «Настройки» или в переменной окружения MAX_BOT_TOKEN (.env)"
            )
            raise ValueError(msg)

        url = f"{self._platform_api_base}/messages"
        params = {"chat_id": chat_id}
        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
        }
        raw_text = (text or "").strip()
        safe = _truncate_utf8_for_max_api(raw_text)
        if safe != raw_text:
            logger.info(
                "MAX send_message: текст усечён по UTF-8 до %s байт (было %s байт), chat_id=%s",
                _MAX_OUTGOING_MESSAGE_UTF8_BYTES,
                len(raw_text.encode("utf-8")),
                chat_id,
            )
        payload = {"text": safe}

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url,
                    params=params,
                    json=payload,
                    headers=headers,
                )
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    logger.error(
                        "MAX send_message: HTTP %s chat_id=%s тело ответа: %s",
                        exc.response.status_code,
                        chat_id,
                        (exc.response.text or "")[:800],
                    )
                    raise
        except httpx.ConnectError as exc:
            logger.error(
                "MAX send_message: нет TCP/TLS до %s (DNS, файрвол, прокси Docker). Подробности: %s",
                url,
                exc,
            )
            raise

    async def send_voice_message(
        self,
        chat_id: int,
        audio_data: bytes,
        *,
        filename: str = "voice.ogg",
    ) -> None:
        """Загружает **Opus OGG** через **POST /uploads?type=audio** и **POST /messages** с вложением **audio** (см. dev.max.ru).

        Имя части multipart на CDN фиксировано (**voice.ogg**); параметр ``filename`` оставлен для совместимости вызовов.
        Промежуточные текстовые уведомления не должны вызывать этот метод — только итоговый ответ бота.
        """
        # TODO (рус.): при смене контракта MAX (поля token/url) сверить с актуальной документацией platform-api.
        token = await self._resolve_bot_token()
        if not token:
            msg = (
                "MAX_BOT_TOKEN не задан: укажите в панели «Настройки» или в переменной окружения MAX_BOT_TOKEN (.env)"
            )
            raise ValueError(msg)
        if not audio_data:
            logger.warning("MAX send_voice_message: пустые аудиоданные, chat_id=%s", chat_id)
            return

        base = self._platform_api_base.rstrip("/")
        uploads_url = f"{base}/uploads"
        messages_url = f"{base}/messages"
        params = {"chat_id": chat_id}

        async with httpx.AsyncClient(timeout=120.0) as client:
            meta = await client.post(
                uploads_url,
                params={"type": "audio"},
                headers={"Authorization": token},
            )
            try:
                meta.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "MAX send_voice_message: получение URL загрузки HTTP %s: %s",
                    exc.response.status_code,
                    (exc.response.text or "")[:800],
                )
                raise

            try:
                meta_body = meta.json()
            except json.JSONDecodeError:
                logger.error("MAX send_voice_message: ответ /uploads не JSON")
                raise ValueError("MAX /uploads: неверный JSON") from None

            upload_url = (meta_body.get("url") or "").strip()
            if not upload_url:
                logger.error("MAX send_voice_message: в ответе /uploads нет поля url: %s", meta_body)
                raise ValueError("MAX /uploads: нет url")

            # Токен вложения иногда приходит сразу в ответе POST /uploads; после загрузки на CDN — в JSON (token / fileId).
            attach_token = (meta_body.get("token") or "").strip() or None

            # Параметр ``filename`` — для совместимости; multipart на CDN всегда **voice.ogg** (см. константы выше).
            want = os.path.basename((filename or "").strip()) or _MAX_VOICE_UPLOAD_FILENAME
            if want != _MAX_VOICE_UPLOAD_FILENAME:
                logger.debug(
                    "MAX send_voice_message: для OK CDN используется имя %s, аргумент filename=%r не применяется",
                    _MAX_VOICE_UPLOAD_FILENAME,
                    filename,
                )

            up = await _post_max_voice_multipart(client, upload_url, audio_data)
            try:
                up.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "MAX send_voice_message: загрузка файла HTTP %s: %s",
                    exc.response.status_code,
                    (exc.response.text or "")[:800],
                )
                raise

            # После успешной загрузки CDN обычно отдаёт JSON с ``token`` или ``fileId``; тело может быть пустым — тогда берём ``token`` из ответа /uploads.
            raw_cdn = (up.text or "").strip()
            cdn_body: Any = None
            if raw_cdn:
                try:
                    cdn_body = json.loads(raw_cdn)
                except json.JSONDecodeError:
                    logger.warning(
                        "MAX send_voice_message: тело CDN не JSON, оставляем token из /uploads; chat_id=%s: %s",
                        chat_id,
                        raw_cdn[:500],
                    )
                else:
                    cdn_token = _max_cdn_attachment_token(cdn_body)
                    if cdn_token:
                        attach_token = cdn_token

            if not attach_token:
                logger.error(
                    "MAX send_voice_message: нет token/fileId ни в /uploads, ни в JSON CDN; "
                    "meta=%s cdn_body=%s",
                    {k: meta_body.get(k) for k in ("url", "token")},
                    cdn_body,
                )
                raise ValueError("MAX: нет идентификатора вложения audio (token/fileId)")

            # Bot API MAX: вложение audio — ``payload.token``; значение берём из ответа CDN как **fileId** или **token**.
            payload = {
                "attachments": [
                    {
                        "type": "audio",
                        "payload": {"token": attach_token},
                    }
                ]
            }
            delays = (0.0, 0.5, 1.0, 2.0, 4.0)
            last_err: str | None = None
            for i, delay_sec in enumerate(delays):
                if delay_sec > 0:
                    await asyncio.sleep(delay_sec)
                resp = await client.post(
                    messages_url,
                    params=params,
                    headers={
                        "Authorization": token,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if resp.status_code < 400:
                    return
                body_snip = (resp.text or "")[:1200]
                last_err = f"HTTP {resp.status_code} {body_snip}"
                low = body_snip.lower()
                if "attachment.not.ready" in low or "not.processed" in low or "file.not.processed" in low:
                    logger.warning(
                        "MAX send_voice_message: вложение ещё не готово (попытка %s/%s), chat_id=%s",
                        i + 1,
                        len(delays),
                        chat_id,
                    )
                    continue
                logger.error(
                    "MAX send_voice_message: отправка сообщения с audio HTTP %s chat_id=%s: %s",
                    resp.status_code,
                    chat_id,
                    body_snip,
                )
                resp.raise_for_status()

            logger.error(
                "MAX send_voice_message: не удалось отправить audio после повторов, chat_id=%s, последняя ошибка=%s",
                chat_id,
                last_err,
            )
            msg = last_err or "MAX: вложение audio не принято после повторов"
            raise RuntimeError(msg)
