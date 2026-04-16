"""МИС: врачи, пациенты, записи, публичная карта, ИИ-консультация."""

from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.api.dependencies import AsyncSessionDep, LLMServiceDep, MaxMessengerClientDep
from src.api.dependencies_portal import PortalUserDep
from src.api.org_scope import resolve_organization_scope
from src.api.schemas.mis import (
    MedicalDoctorCreate,
    MedicalDoctorOut,
    MedicalEntryCreate,
    MedicalEntryOut,
    MedicalPatientAdminCreate,
    MedicalPatientCreate,
    MedicalPatientOut,
    MedicalPatientUpdate,
    MisAiConsultRequest,
    MisAiConsultResponse,
    MisMaxSendRequest,
    PublicHealthDiaryCreate,
    PublicPatientCardResponse,
)
from src.infrastructure.services.shop_order_notify import send_max_order_message
from src.domain.portal_roles import ROLE_ORG_ADMIN, ROLE_SUPER_ADMIN
from src.infrastructure.models import (
    MedicalDoctorModel,
    MedicalEntryModel,
    MedicalEntryType,
    MedicalPatientModel,
    PortalUserModel,
)
router = APIRouter(prefix="/mis", tags=["mis"])
public_router = APIRouter(prefix="/public/mis", tags=["mis-public"])

_MIS_AI_SYSTEM = (
    "Ты — ассистент врача в медицинской информационной системе. "
    "Анализируй предоставленные данные карты и обследований. "
    "Не ставь окончательный диагноз и не назначай лечение вместо лечащего врача; "
    "давай обобщения, гипотезы для обсуждения и напоминания о необходимости очной консультации. "
    "Отвечай на русском языке."
)


def _require_mis_admin(user: PortalUserDep) -> PortalUserModel:
    if user.role not in (ROLE_ORG_ADMIN, ROLE_SUPER_ADMIN):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Недостаточно прав (нужна роль администратора организации)")
    return user


MisAdminDep = Annotated[PortalUserModel, Depends(_require_mis_admin)]


async def get_mis_doctor(
    user: PortalUserDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(None, description="Для super_admin: id организации"),
) -> MedicalDoctorModel:
    scope = resolve_organization_scope(user, organization_id)
    if scope is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Укажите organization_id в query или войдите в контекст организации",
        )
    stmt = select(MedicalDoctorModel).where(
        MedicalDoctorModel.organization_id == scope,
        MedicalDoctorModel.portal_user_id == user.id,
        MedicalDoctorModel.is_active.is_(True),
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Профиль врача МИС не найден. Обратитесь к администратору организации.",
        )
    return row


MisDoctorDep = Annotated[MedicalDoctorModel, Depends(get_mis_doctor)]


def _doctor_out(row: MedicalDoctorModel, display_name: str | None = None) -> MedicalDoctorOut:
    return MedicalDoctorOut(
        id=row.id,
        organization_id=row.organization_id,
        portal_user_id=row.portal_user_id,
        qualification=row.qualification or "",
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
        display_name=display_name,
    )


def _norm_phone(v: str | None) -> str | None:
    s = (v or "").strip()
    return s if s else None


def _patient_out(p: MedicalPatientModel) -> MedicalPatientOut:
    return MedicalPatientOut(
        id=p.id,
        organization_id=p.organization_id,
        doctor_id=p.doctor_id,
        full_name=p.full_name,
        phone=p.phone or "",
        birth_date=p.birth_date,
        gender=p.gender,
        height=p.height,
        weight=p.weight,
        current_diagnosis=p.current_diagnosis or "",
        treatment_plan=p.treatment_plan or "",
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _entry_out(e: MedicalEntryModel) -> MedicalEntryOut:
    t = e.type.value if hasattr(e.type, "value") else str(e.type)
    return MedicalEntryOut(
        id=e.id,
        patient_id=e.patient_id,
        type=t,
        entry_date=e.entry_date,
        data=dict(e.data or {}),
        conclusion=e.conclusion or "",
        recommendations=e.recommendations or "",
        created_at=e.created_at,
    )


@router.get("/admin/doctors", response_model=list[MedicalDoctorOut])
async def mis_admin_list_doctors(
    user: MisAdminDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(None, description="Для super_admin: организация"),
) -> list[MedicalDoctorOut]:
    """Список врачей МИС организации (для админ-панели)."""
    scope = resolve_organization_scope(user, organization_id)
    if scope is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Укажите organization_id или войдите в контекст организации",
        )
    stmt = (
        select(MedicalDoctorModel)
        .where(MedicalDoctorModel.organization_id == scope)
        .order_by(MedicalDoctorModel.created_at.desc())
    )
    rows = (await session.scalars(stmt)).all()
    result: list[MedicalDoctorOut] = []
    for row in rows:
        pu = await session.get(PortalUserModel, row.portal_user_id)
        result.append(_doctor_out(row, display_name=pu.display_name if pu else None))
    return result


@router.post("/admin/doctors", response_model=MedicalDoctorOut, status_code=status.HTTP_201_CREATED)
async def mis_admin_create_doctor(
    body: MedicalDoctorCreate,
    user: MisAdminDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(None, description="Для super_admin: организация"),
) -> MedicalDoctorOut:
    """Добавление врача МИС (привязка пользователя портала к организации)."""
    scope = resolve_organization_scope(user, organization_id)
    if scope is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Укажите organization_id или войдите как пользователь организации",
        )
    pu = await session.get(PortalUserModel, body.portal_user_id)
    if pu is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Пользователь портала не найден")
    if pu.organization_id != scope:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Пользователь не принадлежит выбранной организации",
        )
    existing = await session.scalar(
        select(MedicalDoctorModel.id).where(MedicalDoctorModel.portal_user_id == body.portal_user_id),
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Этот пользователь уже зарегистрирован как врач МИС")
    row = MedicalDoctorModel(
        organization_id=scope,
        portal_user_id=body.portal_user_id,
        qualification=(body.qualification or "").strip(),
        is_active=True,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _doctor_out(row, display_name=pu.display_name)


@router.get("/admin/patients", response_model=list[MedicalPatientOut])
async def mis_admin_list_patients(
    user: MisAdminDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(None, description="Для super_admin: организация"),
) -> list[MedicalPatientOut]:
    """Список всех пациентов организации."""
    scope = resolve_organization_scope(user, organization_id)
    if scope is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Укажите organization_id или войдите в контекст организации",
        )
    stmt = (
        select(MedicalPatientModel)
        .where(MedicalPatientModel.organization_id == scope)
        .order_by(MedicalPatientModel.updated_at.desc())
    )
    rows = (await session.scalars(stmt)).all()
    return [_patient_out(p) for p in rows]


@router.get("/admin/patients/{patient_id}", response_model=PublicPatientCardResponse)
async def mis_admin_get_patient(
    patient_id: UUID,
    user: MisAdminDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(None, description="Для super_admin: организация"),
) -> PublicPatientCardResponse:
    """Карта пациента для администратора организации (все пациенты орг., без профиля врача)."""
    scope = resolve_organization_scope(user, organization_id)
    if scope is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Укажите organization_id или войдите в контекст организации",
        )
    stmt = (
        select(MedicalPatientModel)
        .where(MedicalPatientModel.id == patient_id, MedicalPatientModel.organization_id == scope)
        .options(selectinload(MedicalPatientModel.entries))
    )
    p = (await session.execute(stmt)).scalar_one_or_none()
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Пациент не найден")
    entries = sorted(
        p.entries or [],
        key=lambda e: (e.entry_date, e.created_at),
        reverse=True,
    )
    return PublicPatientCardResponse(patient=_patient_out(p), entries=[_entry_out(e) for e in entries])


@router.post("/admin/patients", response_model=MedicalPatientOut, status_code=status.HTTP_201_CREATED)
async def mis_admin_create_patient(
    body: MedicalPatientAdminCreate,
    user: MisAdminDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(None, description="Для super_admin: организация"),
) -> MedicalPatientOut:
    """Создание пациента админом: карта закрепляется за выбранным врачом МИС."""
    scope = resolve_organization_scope(user, organization_id)
    if scope is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Укажите organization_id или войдите в контекст организации",
        )
    doc = await session.get(MedicalDoctorModel, body.doctor_id)
    if doc is None or doc.organization_id != scope or not doc.is_active:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Врач МИС не найден, не в вашей организации или отключён",
        )
    row = MedicalPatientModel(
        organization_id=scope,
        doctor_id=doc.id,
        full_name=body.full_name.strip(),
        phone=_norm_phone(body.phone),
        birth_date=body.birth_date,
        gender=(body.gender or "").strip() or None,
        height=body.height,
        weight=body.weight,
        current_diagnosis=(body.current_diagnosis or "").strip(),
        treatment_plan=(body.treatment_plan or "").strip(),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _patient_out(row)


@router.patch("/admin/patients/{patient_id}", response_model=MedicalPatientOut)
async def mis_admin_patch_patient(
    patient_id: UUID,
    body: MedicalPatientUpdate,
    user: MisAdminDep,
    session: AsyncSessionDep,
    organization_id: UUID | None = Query(None, description="Для super_admin: организация"),
) -> MedicalPatientOut:
    scope = resolve_organization_scope(user, organization_id)
    if scope is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Укажите organization_id или войдите в контекст организации",
        )
    p = await session.get(MedicalPatientModel, patient_id)
    if p is None or p.organization_id != scope:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Пациент не найден")
    data = body.model_dump(exclude_unset=True)
    if "full_name" in data and data["full_name"] is not None:
        p.full_name = data["full_name"].strip()
    if "phone" in data:
        p.phone = None if data["phone"] is None else _norm_phone(str(data["phone"]))
    if "birth_date" in data:
        p.birth_date = data["birth_date"]
    if "gender" in data:
        p.gender = (data["gender"] or "").strip() or None
    if "height" in data:
        p.height = data["height"]
    if "weight" in data:
        p.weight = data["weight"]
    if "current_diagnosis" in data and data["current_diagnosis"] is not None:
        p.current_diagnosis = data["current_diagnosis"].strip()
    if "treatment_plan" in data and data["treatment_plan"] is not None:
        p.treatment_plan = data["treatment_plan"].strip()
    await session.commit()
    await session.refresh(p)
    return _patient_out(p)


@router.post("/admin/ai-consult", response_model=MisAiConsultResponse)
async def mis_admin_ai_consult(
    body: MisAiConsultRequest,
    user: MisAdminDep,
    session: AsyncSessionDep,
    llm: LLMServiceDep,
    organization_id: UUID | None = Query(None, description="Для super_admin: организация"),
) -> MisAiConsultResponse:
    scope = resolve_organization_scope(user, organization_id)
    if scope is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Укажите organization_id или войдите в контекст организации",
        )
    p = await session.get(MedicalPatientModel, body.patient_id)
    if p is None or p.organization_id != scope:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Пациент не найден")
    stmt = (
        select(MedicalEntryModel)
        .where(MedicalEntryModel.patient_id == p.id)
        .order_by(MedicalEntryModel.entry_date.desc(), MedicalEntryModel.created_at.desc())
    )
    entries = (await session.scalars(stmt)).all()
    patient_block = (
        f"Пациент: {p.full_name}\n"
        f"Телефон: {p.phone or '—'}\n"
        f"Дата рождения: {p.birth_date}\n"
        f"Пол: {p.gender}\n"
        f"Рост/вес: {p.height} / {p.weight}\n"
        f"Диагноз (текущий): {p.current_diagnosis}\n"
        f"План лечения: {p.treatment_plan}\n"
    )
    entry_blocks: list[str] = []
    for e in entries[:50]:
        t = e.type.value if hasattr(e.type, "value") else str(e.type)
        entry_blocks.append(
            f"— {e.entry_date} ({t}):\n"
            f"данные JSON: {json.dumps(e.data or {}, ensure_ascii=False)}\n"
            f"заключение: {e.conclusion}\n"
            f"рекомендации: {e.recommendations}\n",
        )
    context_parts = [patient_block, "История обследований и опросников:\n" + "\n".join(entry_blocks)]
    answer = await llm.generate_response(
        body.question.strip(),
        context_parts,
        system_prompt=_MIS_AI_SYSTEM,
    )
    return MisAiConsultResponse(answer=answer)


@router.post("/admin/patients/{patient_id}/send-max")
async def mis_admin_send_max_summary(
    patient_id: UUID,
    body: MisMaxSendRequest,
    request: Request,
    user: MisAdminDep,
    session: AsyncSessionDep,
    max_client: MaxMessengerClientDep,
    organization_id: UUID | None = Query(None, description="Для super_admin: организация"),
) -> dict[str, bool]:
    scope = resolve_organization_scope(user, organization_id)
    if scope is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Укажите organization_id или войдите в контекст организации",
        )
    if not (await max_client.resolve_bot_token()).strip():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Бот MAX не настроен (MAX_BOT_TOKEN)",
        )
    p = await session.get(MedicalPatientModel, patient_id)
    if p is None or p.organization_id != scope:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Пациент не найден")
    base = str(request.base_url).rstrip("/")
    public_card = f"{base}/public/mis/patient/{p.id}"
    text = (
        f"МИС — сводка по пациенту\n"
        f"ФИО: {p.full_name}\n"
        f"Телефон: {p.phone or '—'}\n"
        f"Диагноз: {(p.current_diagnosis or '').strip() or '—'}\n"
        f"Лечение: {(p.treatment_plan or '').strip() or '—'}\n"
        f"Карта (ссылка для пациента): {public_card}"
    )
    try:
        await send_max_order_message(max_client, body.max_chat_id, text)
    except Exception as e:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"Не удалось отправить сообщение в MAX: {e!s}",
        ) from e
    return {"ok": True}


@router.get("/doctor/patients", response_model=list[MedicalPatientOut])
async def mis_doctor_list_patients(
    doctor: MisDoctorDep,
    session: AsyncSessionDep,
) -> list[MedicalPatientOut]:
    """Список пациентов, закреплённых за текущим врачом."""
    stmt = (
        select(MedicalPatientModel)
        .where(
            MedicalPatientModel.doctor_id == doctor.id,
            MedicalPatientModel.organization_id == doctor.organization_id,
        )
        .order_by(MedicalPatientModel.updated_at.desc())
    )
    rows = (await session.scalars(stmt)).all()
    return [_patient_out(p) for p in rows]


@router.get("/doctor/patients/{patient_id}", response_model=PublicPatientCardResponse)
async def mis_doctor_get_patient(
    patient_id: UUID,
    doctor: MisDoctorDep,
    session: AsyncSessionDep,
) -> PublicPatientCardResponse:
    """Карта пациента и история записей для врача."""
    stmt = (
        select(MedicalPatientModel)
        .where(
            MedicalPatientModel.id == patient_id,
            MedicalPatientModel.doctor_id == doctor.id,
            MedicalPatientModel.organization_id == doctor.organization_id,
        )
        .options(selectinload(MedicalPatientModel.entries))
    )
    p = (await session.execute(stmt)).scalar_one_or_none()
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Пациент не найден")
    entries = sorted(
        p.entries or [],
        key=lambda e: (e.entry_date, e.created_at),
        reverse=True,
    )
    return PublicPatientCardResponse(patient=_patient_out(p), entries=[_entry_out(e) for e in entries])


@router.post("/doctor/patients", response_model=MedicalPatientOut, status_code=status.HTTP_201_CREATED)
async def mis_doctor_create_patient(
    body: MedicalPatientCreate,
    doctor: MisDoctorDep,
    session: AsyncSessionDep,
) -> MedicalPatientOut:
    """Регистрация пациента (назначение на текущего врача)."""
    row = MedicalPatientModel(
        organization_id=doctor.organization_id,
        doctor_id=doctor.id,
        full_name=body.full_name.strip(),
        phone=_norm_phone(body.phone),
        birth_date=body.birth_date,
        gender=(body.gender or "").strip() or None,
        height=body.height,
        weight=body.weight,
        current_diagnosis=(body.current_diagnosis or "").strip(),
        treatment_plan=(body.treatment_plan or "").strip(),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _patient_out(row)


@router.patch("/doctor/patients/{patient_id}", response_model=MedicalPatientOut)
async def mis_doctor_update_patient(
    patient_id: UUID,
    body: MedicalPatientUpdate,
    doctor: MisDoctorDep,
    session: AsyncSessionDep,
) -> MedicalPatientOut:
    """Обновление карты пациента."""
    p = await session.get(MedicalPatientModel, patient_id)
    if p is None or p.doctor_id != doctor.id or p.organization_id != doctor.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Пациент не найден")
    data = body.model_dump(exclude_unset=True)
    if "full_name" in data and data["full_name"] is not None:
        p.full_name = data["full_name"].strip()
    if "phone" in data:
        p.phone = None if data["phone"] is None else _norm_phone(str(data["phone"]))
    if "birth_date" in data:
        p.birth_date = data["birth_date"]
    if "gender" in data:
        p.gender = (data["gender"] or "").strip() or None
    if "height" in data:
        p.height = data["height"]
    if "weight" in data:
        p.weight = data["weight"]
    if "current_diagnosis" in data and data["current_diagnosis"] is not None:
        p.current_diagnosis = data["current_diagnosis"].strip()
    if "treatment_plan" in data and data["treatment_plan"] is not None:
        p.treatment_plan = data["treatment_plan"].strip()
    await session.commit()
    await session.refresh(p)
    return _patient_out(p)


@router.post("/doctor/patients/{patient_id}/entries", response_model=MedicalEntryOut, status_code=status.HTTP_201_CREATED)
async def mis_doctor_add_entry(
    patient_id: UUID,
    body: MedicalEntryCreate,
    doctor: MisDoctorDep,
    session: AsyncSessionDep,
) -> MedicalEntryOut:
    """Добавление записи обследования / опросника."""
    p = await session.get(MedicalPatientModel, patient_id)
    if p is None or p.doctor_id != doctor.id or p.organization_id != doctor.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Пациент не найден")
    et = MedicalEntryType(body.type)
    row = MedicalEntryModel(
        patient_id=p.id,
        type=et,
        entry_date=body.entry_date,
        data=dict(body.data or {}),
        conclusion=(body.conclusion or "").strip(),
        recommendations=(body.recommendations or "").strip(),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _entry_out(row)


@public_router.get("/patient/{patient_id}", response_model=PublicPatientCardResponse)
async def mis_public_patient_card(
    patient_id: UUID,
    session: AsyncSessionDep,
) -> PublicPatientCardResponse:
    """Публичная карта пациента и история (доступ по UUID без авторизации)."""
    stmt = (
        select(MedicalPatientModel)
        .where(MedicalPatientModel.id == patient_id)
        .options(selectinload(MedicalPatientModel.entries))
    )
    p = (await session.execute(stmt)).scalar_one_or_none()
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Карта не найдена")
    entries = sorted(
        p.entries or [],
        key=lambda e: (e.entry_date, e.created_at),
        reverse=True,
    )
    return PublicPatientCardResponse(patient=_patient_out(p), entries=[_entry_out(e) for e in entries])


@public_router.post(
    "/patient/{patient_id}/diary",
    response_model=MedicalEntryOut,
    status_code=status.HTTP_201_CREATED,
)
async def mis_public_health_diary(
    patient_id: UUID,
    body: PublicHealthDiaryCreate,
    session: AsyncSessionDep,
) -> MedicalEntryOut:
    """Пациент добавляет запись дневника здоровья (тип survey, данные в JSON)."""
    p = await session.get(MedicalPatientModel, patient_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Карта не найдена")
    row = MedicalEntryModel(
        patient_id=p.id,
        type=MedicalEntryType.survey,
        entry_date=body.entry_date,
        data={"metric": body.metric.strip(), "value": body.value.strip(), "source": "patient_diary"},
        conclusion="",
        recommendations="",
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _entry_out(row)


@router.post("/doctor/ai-consult", response_model=MisAiConsultResponse)
async def mis_doctor_ai_consult(
    body: MisAiConsultRequest,
    doctor: MisDoctorDep,
    session: AsyncSessionDep,
    llm: LLMServiceDep,
) -> MisAiConsultResponse:
    """ИИ-анализ с контекстом карты пациента и записей обследований."""
    p = await session.get(MedicalPatientModel, body.patient_id)
    if p is None or p.doctor_id != doctor.id or p.organization_id != doctor.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Пациент не найден")
    stmt = (
        select(MedicalEntryModel)
        .where(MedicalEntryModel.patient_id == p.id)
        .order_by(MedicalEntryModel.entry_date.desc(), MedicalEntryModel.created_at.desc())
    )
    entries = (await session.scalars(stmt)).all()

    patient_block = (
        f"Пациент: {p.full_name}\n"
        f"Телефон: {p.phone or '—'}\n"
        f"Дата рождения: {p.birth_date}\n"
        f"Пол: {p.gender}\n"
        f"Рост/вес: {p.height} / {p.weight}\n"
        f"Диагноз (текущий): {p.current_diagnosis}\n"
        f"План лечения: {p.treatment_plan}\n"
    )
    entry_blocks: list[str] = []
    for e in entries[:50]:
        t = e.type.value if hasattr(e.type, "value") else str(e.type)
        entry_blocks.append(
            f"— {e.entry_date} ({t}):\n"
            f"данные JSON: {json.dumps(e.data or {}, ensure_ascii=False)}\n"
            f"заключение: {e.conclusion}\n"
            f"рекомендации: {e.recommendations}\n",
        )
    context_parts = [patient_block, "История обследований и опросников:\n" + "\n".join(entry_blocks)]
    answer = await llm.generate_response(
        body.question.strip(),
        context_parts,
        system_prompt=_MIS_AI_SYSTEM,
    )
    return MisAiConsultResponse(answer=answer)


@router.post("/doctor/patients/{patient_id}/send-max")
async def mis_doctor_send_max_summary(
    patient_id: UUID,
    body: MisMaxSendRequest,
    request: Request,
    doctor: MisDoctorDep,
    session: AsyncSessionDep,
    max_client: MaxMessengerClientDep,
) -> dict[str, bool]:
    """Отправка краткой сводки по пациенту в указанный чат MAX (через ``MaxMessengerClient``)."""
    if not (await max_client.resolve_bot_token()).strip():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Бот MAX не настроен (MAX_BOT_TOKEN)",
        )
    p = await session.get(MedicalPatientModel, patient_id)
    if p is None or p.doctor_id != doctor.id or p.organization_id != doctor.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Пациент не найден")
    base = str(request.base_url).rstrip("/")
    public_card = f"{base}/public/mis/patient/{p.id}"
    text = (
        f"МИС — сводка по пациенту\n"
        f"ФИО: {p.full_name}\n"
        f"Телефон: {p.phone or '—'}\n"
        f"Диагноз: {(p.current_diagnosis or '').strip() or '—'}\n"
        f"Лечение: {(p.treatment_plan or '').strip() or '—'}\n"
        f"Карта (ссылка для пациента): {public_card}"
    )
    try:
        await send_max_order_message(max_client, body.max_chat_id, text)
    except Exception as e:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"Не удалось отправить сообщение в MAX: {e!s}",
        ) from e
    return {"ok": True}
