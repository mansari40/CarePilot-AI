"""Patient data routes — appointments, documents, reminders, insurance, billing."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_patient_profile, get_current_user, get_db
from app.config import get_settings
from app.db.models import (
    Appointment,
    Department,
    Doctor,
    InsurancePolicy,
    PatientDocument,
    PatientProfile,
    Reminder,
    User,
    InsuranceEligibilityCheck,
    BillingExplanation,
    BillingLineItem,
    AuditEvent,
)
from app.schemas.workflow import ReminderRead
from app.tools.appointments import cancel_appointment
from app.tools.documents import DuplicateDocumentError, store_document

from pydantic import BaseModel, ConfigDict
from datetime import datetime


class AppointmentRead(BaseModel):
    id: int
    patient_id: int
    department_id: int
    doctor_id: int | None
    slot_id: int | None
    status: str
    visit_type: str
    reason: str | None
    scheduled_for: datetime | None
    notes: str | None
    created_at: datetime
    department_name: str | None = None
    doctor_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentRead(BaseModel):
    id: int
    patient_id: int
    appointment_id: int | None
    filename: str
    storage_path: str
    document_type: str
    checksum: str
    is_duplicate: bool
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InsurancePolicyRead(BaseModel):
    id: int
    patient_id: int
    provider_name: str
    policy_number: str
    plan_type: str
    active: bool
    valid_from: datetime
    valid_to: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EligibilityCheckRead(BaseModel):
    id: int
    appointment_id: int
    policy_id: int | None
    status: str
    coverage_summary: str | None
    checked_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BillingLineRead(BaseModel):
    id: int
    appointment_id: int
    description: str
    amount_usd: float
    category: str
    source: str | None

    model_config = ConfigDict(from_attributes=True)


class BillingExplanationRead(BaseModel):
    id: int
    appointment_id: int
    summary_text: str
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)


router = APIRouter(prefix="/api/patients/me", tags=["patient-data"])


@router.get("/appointments", response_model=list[AppointmentRead])
def list_my_appointments(
    profile: Annotated[PatientProfile, Depends(get_current_patient_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AppointmentRead]:
    appts = (
        db.query(Appointment)
        .filter(Appointment.patient_id == profile.id)
        .order_by(Appointment.created_at.desc())
        .all()
    )
    result = []
    for a in appts:
        dept = db.get(Department, a.department_id)
        doctor = db.get(Doctor, a.doctor_id) if a.doctor_id else None
        result.append(AppointmentRead(
            id=a.id,
            patient_id=a.patient_id,
            department_id=a.department_id,
            doctor_id=a.doctor_id,
            slot_id=a.slot_id,
            status=a.status,
            visit_type=a.visit_type,
            reason=a.reason,
            scheduled_for=a.scheduled_for,
            notes=a.notes,
            created_at=a.created_at,
            department_name=dept.name if dept else None,
            doctor_name=doctor.name if doctor else None,
        ))
    return result


@router.get("/documents", response_model=list[DocumentRead])
def list_my_documents(
    profile: Annotated[PatientProfile, Depends(get_current_patient_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> list[DocumentRead]:
    docs = (
        db.query(PatientDocument)
        .filter(PatientDocument.patient_id == profile.id)
        .order_by(PatientDocument.uploaded_at.desc())
        .all()
    )
    return [DocumentRead.model_validate(d) for d in docs]


@router.post("/documents", response_model=DocumentRead, status_code=201)
async def upload_document(
    profile: Annotated[PatientProfile, Depends(get_current_patient_profile)],
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File()],
    document_type: Annotated[str, Form()] = "other",
) -> DocumentRead:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    settings = get_settings()
    try:
        doc = store_document(
            db,
            patient_id=profile.id,
            filename=file.filename or "unnamed",
            content=content,
            document_type=document_type,
            upload_dir=settings.upload_dir,
        )
    except DuplicateDocumentError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return DocumentRead.model_validate(doc)


@router.delete("/documents/{doc_id}", status_code=204)
def delete_document(
    doc_id: int,
    profile: Annotated[PatientProfile, Depends(get_current_patient_profile)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    doc = db.get(PatientDocument, doc_id)
    if doc is None or doc.patient_id != profile.id:
        raise HTTPException(status_code=404, detail="Document not found")
    filename = doc.filename
    db.delete(doc)
    db.add(
        AuditEvent(
            actor_user_id=current_user.id,
            action="document_deleted",
            entity_type="patient_document",
            entity_id=doc_id,
            details={"filename": filename, "patient_id": profile.id},
        )
    )
    db.commit()


@router.get("/reminders", response_model=list[ReminderRead])
def list_my_reminders(
    profile: Annotated[PatientProfile, Depends(get_current_patient_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ReminderRead]:
    reminders = (
        db.query(Reminder)
        .filter(Reminder.patient_id == profile.id)
        .order_by(Reminder.scheduled_for.desc())
        .all()
    )
    result = []
    for r in reminders:
        rd = ReminderRead.model_validate(r)
        if r.appointment_id:
            appt = db.get(Appointment, r.appointment_id)
            if appt:
                rd.appointment_date = appt.scheduled_for
        result.append(rd)
    return result


@router.get("/insurance", response_model=list[InsurancePolicyRead])
def list_my_insurance(
    profile: Annotated[PatientProfile, Depends(get_current_patient_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> list[InsurancePolicyRead]:
    policies = (
        db.query(InsurancePolicy)
        .filter(InsurancePolicy.patient_id == profile.id)
        .order_by(InsurancePolicy.created_at.desc())
        .all()
    )
    return [InsurancePolicyRead.model_validate(p) for p in policies]


@router.get("/eligibility", response_model=list[EligibilityCheckRead])
def list_my_eligibility(
    profile: Annotated[PatientProfile, Depends(get_current_patient_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> list[EligibilityCheckRead]:
    appt_ids = [a.id for a in db.query(Appointment.id).filter(Appointment.patient_id == profile.id).all()]
    if not appt_ids:
        return []
    checks = (
        db.query(InsuranceEligibilityCheck)
        .filter(InsuranceEligibilityCheck.appointment_id.in_(appt_ids))
        .order_by(InsuranceEligibilityCheck.checked_at.desc())
        .all()
    )
    return [EligibilityCheckRead.model_validate(c) for c in checks]


@router.post("/appointments/{appointment_id}/cancel", response_model=AppointmentRead)
def cancel_my_appointment(
    appointment_id: int,
    profile: Annotated[PatientProfile, Depends(get_current_patient_profile)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AppointmentRead:
    appt = db.get(Appointment, appointment_id)
    if appt is None or appt.patient_id != profile.id:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appt.status not in ("scheduled", "confirmed", "rescheduled"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel appointment with status '{appt.status}'")
    updated = cancel_appointment(db, appointment_id, reason="Cancelled by patient", actor_user_id=current_user.id)
    dept = db.get(Department, updated.department_id)
    doctor = db.get(Doctor, updated.doctor_id) if updated.doctor_id else None
    return AppointmentRead(
        id=updated.id,
        patient_id=updated.patient_id,
        department_id=updated.department_id,
        doctor_id=updated.doctor_id,
        slot_id=updated.slot_id,
        status=updated.status,
        visit_type=updated.visit_type,
        reason=updated.reason,
        scheduled_for=updated.scheduled_for,
        notes=updated.notes,
        created_at=updated.created_at,
        department_name=dept.name if dept else None,
        doctor_name=doctor.name if doctor else None,
    )


@router.get("/billing", response_model=list[BillingExplanationRead])
def list_my_billing(
    profile: Annotated[PatientProfile, Depends(get_current_patient_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> list[BillingExplanationRead]:
    appt_ids = [a.id for a in db.query(Appointment.id).filter(Appointment.patient_id == profile.id).all()]
    if not appt_ids:
        return []
    explanations = (
        db.query(BillingExplanation)
        .filter(BillingExplanation.appointment_id.in_(appt_ids))
        .order_by(BillingExplanation.generated_at.desc())
        .all()
    )
    return [BillingExplanationRead.model_validate(e) for e in explanations]
