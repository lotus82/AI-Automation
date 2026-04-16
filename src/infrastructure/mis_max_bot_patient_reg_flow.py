"""Регистрация пациента МИС в MAX: /start reg_org_*_doc_* и пошаговый диалог в личном чате."""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.domain import system_setting_keys as sk
from src.infrastructure.max_bot_identity import resolve_max_webhook_organization_id
from src.infrastructure.models import MedicalDoctorModel, MedicalPatientModel
from src.infrastructure.repositories import PostgresSettingsRepository
from src.infrastructure.services.max_incoming_group import detect_max_group_chat
from src.infrastructure.services.max_messenger import MaxMessengerClient

logger = logging.getLogger(__name__)

_START_CMD = re.compile(r"^/start(?:@[\w.-]+)?(?:\s+(?P<payload>.+))?\s*$", re.IGNORECASE)
_REG_DEEP = re.compile(r"^reg_org_([0-9a-fA-F-]{36})_doc_([0-9a-fA-F-]{36})\s*$", re.IGNORECASE)
_REDIS_PREFIX = "mis_max_reg:v1:"
_REDIS_TTL_SEC = 172800  # 48 ч

_STEP_FULL_NAME = "full_name"
_STEP_BIRTH_DATE = "birth_date"
_STEP_HEIGHT = "height"
_STEP_WEIGHT = "weight"
_STEP_PHONE = "phone"


def _norm_phone(v: str | None) -> str | None:
    s = (v or "").strip()
    return s if s else None


def _max_sender_user_id_str(sender: Any) -> str | None:
    if not isinstance(sender, dict) or sender.get("is_bot") is True:
        return None
    for key in ("user_id", "id"):
        if key not in sender:
            continue
        raw = sender[key]
        if raw is None:
            continue
        try:
            return str(int(raw))
        except (TypeError, ValueError):
            s = str(raw).strip()
            if s:
                return s
    nested = sender.get("user")
    if isinstance(nested, dict):
        return _max_sender_user_id_str(nested)
    return None


def _redis_key(chat_id: int) -> str:
    return f"{_REDIS_PREFIX}{chat_id}"


def _normalize_max_update_type(raw: str) -> str:
    s = (raw or "").strip().lower()
    for ch in (" ", "-"):
        s = s.replace(ch, "_")
    return s


def _as_reg_payload_string(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if _REG_DEEP.match(s):
        return s
    return None


def unwrap_max_update_body(raw: dict[str, Any]) -> dict[str, Any]:
    """MAX шлёт объект Update корнем POST; иногда обёртка ``update`` / ``data`` (прокси, старые клиенты)."""
    if not isinstance(raw, dict):
        return {}
    if raw.get("update_type") is not None or raw.get("updateType") is not None:
        return raw
    inner = raw.get("update")
    if isinstance(inner, dict) and (
        inner.get("update_type") is not None
        or inner.get("updateType") is not None
        or inner.get("message") is not None
        or inner.get("payload") is not None
    ):
        return inner
    data = raw.get("data")
    if isinstance(data, dict) and (
        data.get("update_type") is not None
        or data.get("updateType") is not None
        or data.get("message") is not None
    ):
        return data
    return raw


def _max_update_type_from_body(body: dict[str, Any]) -> str:
    raw = body.get("update_type")
    if raw is None:
        raw = body.get("updateType")
    return _normalize_max_update_type(str(raw or ""))


def _reg_payload_from_bot_started_body(body: dict[str, Any]) -> str | None:
    """Поля ``payload`` / ``start`` / camelCase — см. [диплинки MAX](https://dev.max.ru/docs/chatbots/bots-coding/prepare)."""
    for key in (
        "payload",
        "start",
        "start_param",
        "startParam",
        "startapp",
        "startApp",
        "args",
    ):
        hit = _as_reg_payload_string(body.get(key))
        if hit:
            return hit
    return None


def _chat_id_from_bot_started_body(body: dict[str, Any]) -> int | None:
    for key in ("chat_id", "chatId"):
        if key not in body:
            continue
        try:
            cid = int(body[key])
        except (TypeError, ValueError):
            continue
        if cid >= 0:
            return cid
    chat = body.get("chat")
    if isinstance(chat, dict):
        for key in ("id", "chat_id", "chatId"):
            if key not in chat:
                continue
            try:
                cid = int(chat[key])
            except (TypeError, ValueError):
                continue
            if cid >= 0:
                return cid
    return None


def _reg_payload_from_message_struct(msg: dict[str, Any]) -> str | None:
    """Параметр диплинка из JSON MAX (не только ``/start`` в ``body.text``)."""

    for key in ("start_param", "startParam", "startapp", "startApp", "payload", "start"):
        hit = _as_reg_payload_string(msg.get(key))
        if hit:
            return hit
    b = msg.get("body")
    if isinstance(b, dict):
        for key in ("start_param", "startParam", "startapp", "startApp", "payload", "start"):
            hit = _as_reg_payload_string(b.get(key))
            if hit:
                return hit
    link = msg.get("link")
    if isinstance(link, dict):
        for key in ("payload", "start_param", "startParam", "start", "startApp"):
            hit = _as_reg_payload_string(link.get(key))
            if hit:
                return hit
        url = link.get("url") or link.get("href") or ""
        if isinstance(url, str) and url.strip():
            try:
                q = parse_qs(urlparse(url.strip()).query)
                for v in q.get("start", []) or []:
                    hit = _as_reg_payload_string(v)
                    if hit:
                        return hit
            except Exception:
                pass
    return None


def _parse_birth_date(text: str) -> tuple[date | None, bool]:
    """(значение или None при пропуске, успех_разбора)."""
    s = (text or "").strip().lower()
    if s in ("", "нет", "-", "не знаю", "пропустить", "н"):
        return None, True
    raw = (text or "").strip()
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date(), True
        except ValueError:
            continue
    return None, False


def _parse_optional_float(text: str) -> tuple[float | None, bool]:
    s = (text or "").strip().lower()
    if s in ("", "нет", "-", "не знаю", "пропустить", "н"):
        return None, True
    try:
        return float((text or "").strip().replace(",", ".")), True
    except ValueError:
        return None, False


async def _find_patient_for_max_identity(
    session: AsyncSession,
    organization_id: UUID,
    chat_id: int,
    max_user_id_str: str | None,
) -> MedicalPatientModel | None:
    cid = str(chat_id)
    if max_user_id_str:
        stmt = select(MedicalPatientModel).where(
            MedicalPatientModel.organization_id == organization_id,
            MedicalPatientModel.max_user_id == max_user_id_str,
        )
        row = (await session.scalars(stmt)).first()
        if row is not None:
            return row
    stmt = select(MedicalPatientModel).where(
        MedicalPatientModel.organization_id == organization_id,
        MedicalPatientModel.max_chat_id == cid,
    )
    return (await session.scalars(stmt)).first()


def _registered_patient_message(settings: Settings, org_id: UUID, patient_id: UUID) -> str:
    lines = [
        "Вы уже зарегистрированы в личном кабинете пациента.",
        "",
    ]
    mini = (settings.mis_max_patient_mini_app_base_url or "").strip().rstrip("/")
    pub = (settings.mis_patient_public_base_url or "").strip().rstrip("/")
    if mini:
        sep = "?" if "?" not in mini else "&"
        lines.append(f"Мини-приложение: {mini}{sep}organization_id={org_id}")
    if pub:
        lines.append(f"Карта в браузере: {pub}/public/mis/patient/{patient_id}")
    if not mini and not pub:
        lines.append(
            "Откройте мини-приложение клиники из меню бота или используйте ссылку на карту, которую присылал врач."
        )
    return "\n".join(lines)


def _new_patient_success_message(
    settings: Settings,
    org_id: UUID,
    patient_id: UUID,
    startapp_token: str,
) -> str:
    lines = [
        "Регистрация завершена. Добро пожаловать!",
        "",
    ]
    mini = (settings.mis_max_patient_mini_app_base_url or "").strip().rstrip("/")
    pub = (settings.mis_patient_public_base_url or "").strip().rstrip("/")
    if mini:
        sep = "&" if "?" in mini else "?"
        lines.append(f"Мини-приложение (как при первом входе): {mini}{sep}startapp={startapp_token}")
        q = "?" if "?" not in mini else "&"
        lines.append(f"Мини-приложение: {mini}{q}organization_id={org_id}")
    if pub:
        lines.append(f"Карта в браузере: {pub}/public/mis/patient/{patient_id}")
    if not mini and not pub:
        lines.append(
            "Укажите в .env MIS_MAX_PATIENT_MINI_APP_BASE_URL и MIS_PATIENT_PUBLIC_BASE_URL — "
            "тогда ссылки будут подставляться автоматически."
        )
    return "\n".join(lines)


def _prompt_for_step(step: str) -> str:
    if step == _STEP_FULL_NAME:
        return (
            "Здравствуйте! Регистрация в кабинете пациента.\n\n"
            "Укажите ФИО полностью.\n\n"
            "Отмена: /cancel"
        )
    if step == _STEP_BIRTH_DATE:
        return "Дата рождения (ДД.ММ.ГГГГ или ГГГГ-ММ-ДД). Можно написать «нет», если не хотите указывать."
    if step == _STEP_HEIGHT:
        return "Рост в см (например 175). «нет» — пропустить."
    if step == _STEP_WEIGHT:
        return "Вес в кг (например 72). «нет» — пропустить."
    if step == _STEP_PHONE:
        return "Телефон для связи (например +7…)."
    return "Продолжим регистрацию."


async def _load_state(redis: Any, chat_id: int) -> dict[str, Any] | None:
    raw = await redis.get(_redis_key(chat_id))
    if not raw:
        return None
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def _save_state(redis: Any, chat_id: int, state: dict[str, Any]) -> None:
    await redis.setex(_redis_key(chat_id), _REDIS_TTL_SEC, json.dumps(state, ensure_ascii=False))


async def _clear_state(redis: Any, chat_id: int) -> None:
    await redis.delete(_redis_key(chat_id))


async def _process_wizard_reply(
    *,
    session: AsyncSession,
    redis: Any,
    settings: Settings,
    max_client: MaxMessengerClient,
    chat_id: int,
    text: str,
    max_user_id_str: str | None,
) -> bool:
    state = await _load_state(redis, chat_id)
    if not state:
        return False

    step = state.get("step")
    org_id = UUID(str(state["org_id"]))
    doc_id = UUID(str(state["doc_id"]))

    if text.strip().lower() in ("/cancel", "отмена"):
        await _clear_state(redis, chat_id)
        await max_client.send_message(chat_id, "Регистрация отменена. Чтобы начать снова, перейдите по ссылке от врача.")
        return True

    if step == _STEP_FULL_NAME:
        fn = text.strip()
        if len(fn) < 3:
            await max_client.send_message(chat_id, "ФИО слишком короткое. Введите полностью (не меньше 3 символов).")
            return True
        state["full_name"] = fn
        state["step"] = _STEP_BIRTH_DATE
        await _save_state(redis, chat_id, state)
        await max_client.send_message(chat_id, _prompt_for_step(_STEP_BIRTH_DATE))
        return True

    if step == _STEP_BIRTH_DATE:
        bd, ok = _parse_birth_date(text)
        if not ok:
            await max_client.send_message(
                chat_id,
                "Не удалось разобрать дату. Пример: 15.03.1990 или 1990-03-15. Или напишите «нет».",
            )
            return True
        state["birth_date"] = bd.isoformat() if bd else None
        state["step"] = _STEP_HEIGHT
        await _save_state(redis, chat_id, state)
        await max_client.send_message(chat_id, _prompt_for_step(_STEP_HEIGHT))
        return True

    if step == _STEP_HEIGHT:
        h, ok = _parse_optional_float(text)
        if not ok:
            await max_client.send_message(chat_id, "Введите число (рост в см) или «нет».")
            return True
        state["height"] = h
        state["step"] = _STEP_WEIGHT
        await _save_state(redis, chat_id, state)
        await max_client.send_message(chat_id, _prompt_for_step(_STEP_WEIGHT))
        return True

    if step == _STEP_WEIGHT:
        w, ok = _parse_optional_float(text)
        if not ok:
            await max_client.send_message(chat_id, "Введите число (вес в кг) или «нет».")
            return True
        state["weight"] = w
        state["step"] = _STEP_PHONE
        await _save_state(redis, chat_id, state)
        await max_client.send_message(chat_id, _prompt_for_step(_STEP_PHONE))
        return True

    if step == _STEP_PHONE:
        phone = _norm_phone(text)
        if not phone or len(phone) < 5:
            await max_client.send_message(chat_id, "Укажите корректный телефон (минимум 5 символов).")
            return True

        doc = await session.get(MedicalDoctorModel, doc_id)
        if doc is None or doc.organization_id != org_id or not doc.is_active:
            await _clear_state(redis, chat_id)
            await max_client.send_message(chat_id, "Врач из приглашения недоступен. Обратитесь в клинику.")
            return True

        birth: date | None = None
        if state.get("birth_date"):
            try:
                birth = date.fromisoformat(str(state["birth_date"]))
            except ValueError:
                birth = None

        row = MedicalPatientModel(
            organization_id=org_id,
            doctor_id=doc_id,
            full_name=str(state["full_name"]).strip(),
            phone=phone,
            birth_date=birth,
            height=state.get("height"),
            weight=state.get("weight"),
            max_user_id=max_user_id_str,
            max_chat_id=str(chat_id),
        )
        session.add(row)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            await _clear_state(redis, chat_id)
            logger.warning(
                "MAX МИС регистрация: конфликт уникальности (телефон или max_user), chat_id=%s",
                chat_id,
            )
            await max_client.send_message(
                chat_id,
                "Не удалось сохранить: этот телефон или аккаунт MAX уже привязаны к карте в клинике. "
                "Обратитесь к администратору или откройте уже созданную карту по ссылке от врача.",
            )
            return True

        await session.refresh(row)
        await _clear_state(redis, chat_id)
        token = f"reg_org_{org_id}_doc_{doc_id}"
        msg = _new_patient_success_message(settings, org_id, row.id, token)
        try:
            await max_client.send_message(chat_id, msg)
        except Exception:
            logger.exception("MAX МИС: не удалось отправить финальное сообщение chat_id=%s", chat_id)
        return True

    logger.warning("MAX МИС мастер: неизвестный шаг %r chat_id=%s", step, chat_id)
    await _clear_state(redis, chat_id)
    await max_client.send_message(
        chat_id,
        "Сессия регистрации устарела. Перейдите по ссылке от врача ещё раз.",
    )
    return True


async def _mis_run_start_registration(
    *,
    session: AsyncSession,
    redis: Any,
    settings: Settings,
    query_organization_id: UUID | None,
    body_for_org_resolve: dict[str, Any],
    org_id: UUID,
    doc_id: UUID,
    chat_id: int,
    max_uid: str | None,
) -> dict[str, Any]:
    """Общая логика: уже есть карта → ссылки; иначе мастер регистрации."""
    org_scope = await resolve_max_webhook_organization_id(
        session,
        body_for_org_resolve,
        query_organization_id=query_organization_id,
    )
    if org_scope is not None and org_scope != org_id:
        logger.warning(
            "MAX МИС регистрация: organization_id из deep link %s не совпадает с организацией бота %s",
            org_id,
            org_scope,
        )

    repo = PostgresSettingsRepository(session, redis, organization_id=org_id)
    token = (await repo.get_value(sk.MAX_BOT_TOKEN) or "").strip()
    if not token:
        logger.warning("MAX МИС регистрация: нет MAX_BOT_TOKEN для organization_id=%s", org_id)
        return {"ok": True, "skipped": True, "reason": "no_max_bot_token"}

    max_client = MaxMessengerClient(
        settings_repository=repo,
        api_base_url=settings.max_api_base,
        platform_api_base_url=settings.max_platform_api_base,
        env_fallback_max_bot_token=settings.max_bot_token,
    )

    existing = await _find_patient_for_max_identity(session, org_id, chat_id, max_uid)
    if existing is not None:
        try:
            if existing.max_chat_id != str(chat_id) or (max_uid and existing.max_user_id != max_uid):
                if existing.max_chat_id != str(chat_id):
                    existing.max_chat_id = str(chat_id)
                if max_uid and not (existing.max_user_id or "").strip():
                    existing.max_user_id = max_uid
                await session.commit()
        except IntegrityError:
            await session.rollback()
            logger.exception("MAX МИС: не удалось обновить привязку чата для patient_id=%s", existing.id)

        out = _registered_patient_message(settings, org_id, existing.id)
        try:
            await max_client.send_message(chat_id, out)
        except Exception:
            logger.exception("MAX МИС: ошибка отправки (уже зарег.), chat_id=%s", chat_id)
            return {"ok": True, "mis_patient_start": False, "send_error": True}
        return {"ok": True, "mis_patient_registration": "existing"}

    doc = await session.get(MedicalDoctorModel, doc_id)
    if doc is None or doc.organization_id != org_id or not doc.is_active:
        try:
            await max_client.send_message(
                chat_id,
                "Врач из приглашения не найден или недоступен. Попросите у клиники новую ссылку.",
            )
        except Exception:
            logger.exception("MAX МИС: ошибка отправки (врач недоступен), chat_id=%s", chat_id)
        return {"ok": True, "mis_patient_registration": "doctor_missing"}

    await _clear_state(redis, chat_id)
    state = {
        "org_id": str(org_id),
        "doc_id": str(doc_id),
        "step": _STEP_FULL_NAME,
    }
    await _save_state(redis, chat_id, state)

    try:
        await max_client.send_message(chat_id, _prompt_for_step(_STEP_FULL_NAME))
    except Exception:
        logger.exception("MAX МИС: ошибка отправки (начало мастера), chat_id=%s", chat_id)
        await _clear_state(redis, chat_id)
        return {"ok": True, "mis_patient_start": False, "send_error": True}

    return {"ok": True, "mis_patient_registration": "wizard_started"}


async def _mis_handle_bot_started(
    body: dict[str, Any],
    *,
    session: AsyncSession,
    redis: Any,
    settings: Settings,
    query_organization_id: UUID | None,
) -> dict[str, Any] | None:
    """Событие ``bot_started``: диплинк ``?start=…`` — поле ``payload`` (см. [документацию MAX](https://dev.max.ru/docs/chatbots/bots-coding/prepare))."""
    arg = _reg_payload_from_bot_started_body(body)
    if not arg:
        logger.info(
            "MAX МИС: bot_started без reg_org_*_doc_* payload (нужен диплинк врача и ``bot_started`` в update_types подписки)",
        )
        return None

    m_reg = _REG_DEEP.match(arg)
    if not m_reg:
        return None

    chat_id = _chat_id_from_bot_started_body(body)
    if chat_id is None:
        logger.warning("MAX МИС: bot_started без chat_id в известных полях")
        return None

    user = body.get("user")
    max_uid = _max_sender_user_id_str(user if isinstance(user, dict) else None)

    org_id = UUID(m_reg.group(1))
    doc_id = UUID(m_reg.group(2))

    return await _mis_run_start_registration(
        session=session,
        redis=redis,
        settings=settings,
        query_organization_id=query_organization_id,
        body_for_org_resolve=body,
        org_id=org_id,
        doc_id=doc_id,
        chat_id=chat_id,
        max_uid=max_uid,
    )


async def try_max_bot_mis_patient_registration_flow(
    body: dict[str, Any],
    *,
    session: AsyncSession,
    redis: Any,
    settings: Settings,
    query_organization_id: UUID | None,
) -> dict[str, Any] | None:
    """Обрабатывает ``bot_started``, ``/start`` с reg_org… и пошаговый диалог в личном чате."""
    body = unwrap_max_update_body(body)
    ut = _max_update_type_from_body(body)
    if ut == "bot_started":
        started = await _mis_handle_bot_started(
            body,
            session=session,
            redis=redis,
            settings=settings,
            query_organization_id=query_organization_id,
        )
        return started

    if ut != "message_created":
        return None
    msg = body.get("message")
    if not isinstance(msg, dict):
        return None
    sender = msg.get("sender")
    is_bot_sender = isinstance(sender, dict) and sender.get("is_bot") is True
    recipient = msg.get("recipient")
    if not isinstance(recipient, dict):
        return None
    chat_id_raw = recipient.get("chat_id")
    if chat_id_raw is None:
        chat_id_raw = recipient.get("chatId")
    if chat_id_raw is None:
        return None
    try:
        chat_id = int(chat_id_raw)
    except (TypeError, ValueError):
        return None

    is_group = detect_max_group_chat(
        chat_id=chat_id,
        recipient=recipient,
        sender=sender if isinstance(sender, dict) else None,
    )
    if is_group:
        return None

    b = msg.get("body")
    text = (b.get("text") or "").strip() if isinstance(b, dict) else ""
    embedded_reg = _reg_payload_from_message_struct(msg)
    if is_bot_sender and not embedded_reg:
        return None
    if embedded_reg:
        m_start = _START_CMD.match(text)
        payload_from_text = (m_start.group("payload") or "").strip() if m_start else ""
        if not _REG_DEEP.match(payload_from_text):
            text = f"/start {embedded_reg}"
    if not text:
        return None

    max_uid = _max_sender_user_id_str(sender if isinstance(sender, dict) else None)

    m_start = _START_CMD.match(text)
    payload_arg = (m_start.group("payload") or "").strip() if m_start else ""
    m_reg = _REG_DEEP.match(payload_arg)
    is_our_start = bool(m_start and m_reg)

    if not is_our_start:
        pending = await _load_state(redis, chat_id)
        if pending:
            try:
                org_from_state = UUID(str(pending["org_id"]))
            except (KeyError, ValueError):
                await _clear_state(redis, chat_id)
                return None
            repo_w = PostgresSettingsRepository(session, redis, organization_id=org_from_state)
            if not (await repo_w.get_value(sk.MAX_BOT_TOKEN) or "").strip():
                await _clear_state(redis, chat_id)
                return None
            max_client_w = MaxMessengerClient(
                settings_repository=repo_w,
                api_base_url=settings.max_api_base,
                platform_api_base_url=settings.max_platform_api_base,
                env_fallback_max_bot_token=settings.max_bot_token,
            )
            if await _process_wizard_reply(
                session=session,
                redis=redis,
                settings=settings,
                max_client=max_client_w,
                chat_id=chat_id,
                text=text,
                max_user_id_str=max_uid,
            ):
                return {"ok": True, "mis_patient_registration": "wizard"}
        return None

    org_id = UUID(m_reg.group(1))
    doc_id = UUID(m_reg.group(2))

    return await _mis_run_start_registration(
        session=session,
        redis=redis,
        settings=settings,
        query_organization_id=query_organization_id,
        body_for_org_resolve=body,
        org_id=org_id,
        doc_id=doc_id,
        chat_id=chat_id,
        max_uid=max_uid,
    )
