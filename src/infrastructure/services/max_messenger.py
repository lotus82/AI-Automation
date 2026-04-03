"""HTTP-клиент к Bot API мессенджера MAX (VK): только httpx, без сторонних обёрток.

Long polling GET ``/updates`` на ``platform-api.max.ru`` — транспортный слой; сценарий ответа тот же, что у POST ``/api/max/webhook``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from collections import Counter
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

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
_POLL_TYPES = ("message_created", "message_callback")


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
        user_info: str | None = None
        if isinstance(sender, dict):
            user_info = (
                (sender.get("name") or sender.get("first_name") or "").strip() or None
            )
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
        user_info = None
        if isinstance(cb_user, dict):
            user_info = (
                (cb_user.get("name") or cb_user.get("first_name") or "").strip() or None
            )
        cid = int(chat_id)
        is_group = detect_max_group_chat(
            chat_id=cid,
            recipient=recipient,
            sender=cb_user if isinstance(cb_user, dict) else None,
        )
        return cid, payload_str, user_info, is_group

    return None


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

    async def _db_allows_long_polling(self) -> bool:
        """Читает **MAX_USE_POLLING** из БД (и Redis-кэш репозитория)."""
        raw = await self._settings_repo.get_value(sk.MAX_USE_POLLING)
        if raw is None or not str(raw).strip():
            return True
        low = str(raw).strip().lower()
        return low not in ("0", "false", "no", "off")

    async def start_polling(
        self,
        use_case: ProcessTextMessageUseCase,
        *,
        session: AsyncSession,
        stop_event: asyncio.Event,
    ) -> None:
        """Бесконечный long poll ``GET /updates``; для каждого события — ``use_case.execute`` + ``send_message``.

        Один цикл жизни **AsyncSession** на процесс (см. ``lifespan``): после каждой успешной пары реплик — ``commit``.
        """
        # TODO (рус.): Если пользователь захочет использовать официальную JS-библиотеку MAX, потребуется вынести этот поллинг в отдельный Node.js микросервис, который будет проксировать запросы на локальный FastAPI вебхук.
        marker: int | None = None
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
                try:
                    reply = await use_case.execute(
                        processed,
                        session_id,
                        interaction_user_label=user_label,
                        append_text_messenger_system_supplement=True,
                    )
                    await self.send_message(chat_id, reply)
                    await session.commit()
                    replies_sent += 1
                    logger.info(
                        "MAX long poll: ответ отправлен chat_id=%s len(reply)=%s instance=%s",
                        chat_id,
                        len(reply or ""),
                        instance_tag,
                    )
                except Exception:
                    await session.rollback()
                    logger.exception("Сбой обработки обновления MAX (long poll), chat_id=%s", chat_id)
                    await asyncio.sleep(5)

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
        payload = {"text": (text or "")[:4000]}

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url,
                    params=params,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.ConnectError as exc:
            logger.error(
                "MAX send_message: нет TCP/TLS до %s (DNS, файрвол, прокси Docker). Подробности: %s",
                url,
                exc,
            )
            raise
