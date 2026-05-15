"""Авторизация пациента МИС через мини-приложение MAX (initData + JWT)."""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.api.dependencies import AsyncSessionDep, RedisDep, SettingsDep
from src.api.dependencies_mis_patient import MisPatientDep
from src.api.routers.mis import _norm_phone, _patient_out
from src.api.schemas.mis import MedicalPatientOut, MedicalPatientPortalSelfUpdate
from src.domain import system_setting_keys as sk
from src.infrastructure.max_webapp_validation import (
    max_init_data_max_user_id,
    max_init_data_start_param,
    validate_max_webapp_init_data,
)
from src.infrastructure.models import MedicalDoctorModel, MedicalPatientModel
from src.infrastructure.miniapp_birth_date_sync import sync_birth_date_by_chat
from src.infrastructure.portal_security import create_mis_patient_access_token
from src.infrastructure.repositories import PostgresSettingsRepository

router = APIRouter(prefix="/mis", tags=["mis-patient-auth"])

_REG_START_PARAM = re.compile(r"^reg_org_([0-9a-fA-F-]{36})_doc_([0-9a-fA-F-]{36})\s*$")


class MaxPatientInitResponse(BaseModel):
    need_registration: bool
    organization_id: UUID
    access_token: str | None = None
    token_type: str | None = None
    patient_id: UUID | None = None
    max_user_id: str | None = None
    start_param: str | None = None
    expires_in_minutes: int | None = None


class MaxPatientRegisterBody(BaseModel):
    organization_id: UUID
    init_data: str = Field(..., min_length=8, description="Та же строка window.WebApp.initData, что при /auth/max/init")
    full_name: str = Field(..., min_length=1, max_length=512)
    phone: str = Field(..., min_length=5, max_length=64)
    confirm_doctor: bool = Field(..., description="Подтверждение привязки к врачу из приглашения")


@router.get("/auth/max/init", response_model=MaxPatientInitResponse)
async def mis_max_patient_auth_init(
    session: AsyncSessionDep,
    redis: RedisDep,
    settings: SettingsDep,
    organization_id: UUID = Query(..., description="Организация (клиника), в контексте которой ищется пациент"),
    init_data: str | None = Query(
        None,
        description="Строка window.WebApp.initData (короткие значения; иначе заголовок)",
        max_length=16000,
    ),
    x_max_init_data: str | None = Header(
        None,
        alias="X-Max-Init-Data",
        description="Полная строка initData (предпочтительно для длинных payload)",
    ),
) -> MaxPatientInitResponse:
    """Инициализация сессии пациента в Mini App MAX: проверка подписи initData, выдача JWT или ``need_registration``."""
    raw = (x_max_init_data or init_data or "").strip()
    if not raw:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Укажите init_data в query или передайте заголовок X-Max-Init-Data",
        )
    repo = PostgresSettingsRepository(session, redis, organization_id=organization_id)
    bot_token = (await repo.get_value(sk.MAX_BOT_TOKEN) or "").strip()
    if not bot_token:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Для организации не настроен MAX_BOT_TOKEN",
        )
    fields = validate_max_webapp_init_data(
        raw,
        bot_token,
        max_age_sec=settings.mis_max_init_data_max_age_sec,
    )
    if not fields:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Недействительная или просроченная подпись initData (MAX)",
        )
    max_uid = max_init_data_max_user_id(fields)
    if not max_uid:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="В initData отсутствует user.id",
        )
    start_param = max_init_data_start_param(fields)

    stmt = select(MedicalPatientModel).where(
        MedicalPatientModel.organization_id == organization_id,
        MedicalPatientModel.max_user_id == max_uid,
    )
    row = (await session.scalars(stmt)).first()
    if row is None:
        return MaxPatientInitResponse(
            need_registration=True,
            organization_id=organization_id,
            max_user_id=max_uid,
            start_param=start_param,
        )

    expire_minutes = settings.mis_patient_jwt_expire_minutes
    token = create_mis_patient_access_token(
        patient_id=row.id,
        organization_id=organization_id,
        secret=settings.portal_jwt_secret,
        expire_minutes=expire_minutes,
    )
    return MaxPatientInitResponse(
        need_registration=False,
        organization_id=organization_id,
        access_token=token,
        token_type="bearer",
        patient_id=row.id,
        start_param=start_param,
        expires_in_minutes=expire_minutes,
    )


@router.post("/auth/max/register", response_model=MaxPatientInitResponse)
async def mis_max_patient_register(
    body: MaxPatientRegisterBody,
    session: AsyncSessionDep,
    redis: RedisDep,
    settings: SettingsDep,
) -> MaxPatientInitResponse:
    """Регистрация пациента по initData MAX и приглашению ``reg_org_<org>_doc_<doctor>`` в start_param."""
    raw = body.init_data.strip()
    repo = PostgresSettingsRepository(session, redis, organization_id=body.organization_id)
    bot_token = (await repo.get_value(sk.MAX_BOT_TOKEN) or "").strip()
    if not bot_token:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Для организации не настроен MAX_BOT_TOKEN",
        )
    fields = validate_max_webapp_init_data(
        raw,
        bot_token,
        max_age_sec=settings.mis_max_init_data_max_age_sec,
    )
    if not fields:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Недействительная или просроченная подпись initData (MAX)",
        )
    max_uid = max_init_data_max_user_id(fields)
    if not max_uid:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="В initData отсутствует user.id",
        )
    start_param = (max_init_data_start_param(fields) or "").strip()
    m = _REG_START_PARAM.match(start_param)
    if not m:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Откройте приглашение из чата MAX (в start_param нет reg_org_…_doc_…)",
        )
    org_from_link = UUID(m.group(1))
    doctor_id = UUID(m.group(2))
    if org_from_link != body.organization_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="organization_id не совпадает с приглашением",
        )

    existing_max = (
        await session.scalars(
            select(MedicalPatientModel).where(
                MedicalPatientModel.organization_id == body.organization_id,
                MedicalPatientModel.max_user_id == max_uid,
            )
        )
    ).first()
    if existing_max is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Этот аккаунт MAX уже привязан к карте. Войдите снова.",
        )

    doc = await session.get(MedicalDoctorModel, doctor_id)
    if doc is None or doc.organization_id != body.organization_id or not doc.is_active:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Врач из приглашения не найден или недоступен",
        )
    if not body.confirm_doctor:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Подтвердите привязку к лечащему врачу",
        )
    phone = _norm_phone(body.phone)
    if not phone:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Укажите номер телефона",
        )

    row = MedicalPatientModel(
        organization_id=body.organization_id,
        doctor_id=doctor_id,
        full_name=body.full_name.strip(),
        phone=phone,
        max_user_id=max_uid,
    )
    session.add(row)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Пациент с таким телефоном или MAX уже есть в организации",
        ) from None
    await session.refresh(row)

    expire_minutes = settings.mis_patient_jwt_expire_minutes
    token = create_mis_patient_access_token(
        patient_id=row.id,
        organization_id=body.organization_id,
        secret=settings.portal_jwt_secret,
        expire_minutes=expire_minutes,
    )
    return MaxPatientInitResponse(
        need_registration=False,
        organization_id=body.organization_id,
        access_token=token,
        token_type="bearer",
        patient_id=row.id,
        max_user_id=max_uid,
        start_param=start_param,
        expires_in_minutes=expire_minutes,
    )


@router.get("/patient-session/me", response_model=MedicalPatientOut)
async def mis_patient_session_me(patient: MisPatientDep) -> MedicalPatientOut:
    """Пример защищённого эндпоинта личного кабинета (только JWT ``mis_patient``)."""
    return _patient_out(patient)


@router.patch("/patient-session/me", response_model=MedicalPatientOut)
async def mis_patient_session_update_me(
    body: MedicalPatientPortalSelfUpdate,
    patient: MisPatientDep,
    session: AsyncSessionDep,
) -> MedicalPatientOut:
    """Обновление ФИО, контактов и антропометрии пациентом (без диагноза и плана лечения)."""
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Нет полей для обновления",
        )
    if "full_name" in data and data["full_name"] is not None:
        patient.full_name = data["full_name"].strip()
    if "phone" in data:
        patient.phone = None if data["phone"] is None else _norm_phone(str(data["phone"]))
    if "birth_date" in data:
        patient.birth_date = data["birth_date"]
        await sync_birth_date_by_chat(
            session,
            organization_id=patient.organization_id,
            chat_id=patient.max_chat_id,
            birth_date=patient.birth_date,
        )
    if "height" in data:
        patient.height = data["height"]
    if "weight" in data:
        patient.weight = data["weight"]
    await session.commit()
    await session.refresh(patient)
    return _patient_out(patient)
