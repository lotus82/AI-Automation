"""HTTP-клиент к Bot API мессенджера MAX (VK): только httpx, без сторонних обёрток.

Long polling GET ``/updates`` на ``platform-api.max.ru`` — транспортный слой; сценарий ответа тот же, что у POST ``/api/max/webhook``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain import system_setting_keys as sk
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


def parse_max_webhook_incoming(payload: dict[str, Any]) -> tuple[int, str, str | None] | None:
    """Извлекает ``chat_id``, текст и подпись пользователя (для мониторинга и ``user_display``).

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
        text = (body.get("text") or "").strip()
        if not text:
            return None
        user_info: str | None = None
        if isinstance(sender, dict):
            user_info = (
                (sender.get("name") or sender.get("first_name") or "").strip() or None
            )
        return int(chat_id), text, user_info

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
        return int(chat_id), payload_str, user_info

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

        while not stop_event.is_set():
            try:
                if not await self._db_allows_long_polling():
                    await asyncio.sleep(5)
                    continue

                token = await self._resolve_bot_token()
                if not token:
                    await asyncio.sleep(10)
                    continue

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

            m_raw = body.get("marker")
            if m_raw is not None:
                try:
                    marker = int(m_raw)
                except (TypeError, ValueError):
                    pass

            for raw_update in body.get("updates") or []:
                if stop_event.is_set():
                    break
                if not isinstance(raw_update, dict):
                    continue
                parsed = parse_max_webhook_incoming(raw_update)
                if parsed is None:
                    continue
                chat_id, user_text, user_label = parsed
                session_id = str(chat_id)
                try:
                    reply = await use_case.execute(
                        user_text,
                        session_id,
                        interaction_user_label=user_label,
                        append_text_messenger_system_supplement=True,
                    )
                    await self.send_message(chat_id, reply)
                    await session.commit()
                except Exception:
                    await session.rollback()
                    logger.exception("Сбой обработки обновления MAX (long poll), chat_id=%s", chat_id)
                    await asyncio.sleep(5)

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
