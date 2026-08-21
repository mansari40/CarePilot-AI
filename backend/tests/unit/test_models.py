"""CRUD tests for every core entity, run directly against PostgreSQL."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, inspect, select

from app.db.models import (
    Appointment,
    AppointmentSlot,
    AuditEvent,
    BillingExplanation,
    BillingLineItem,
    Department,
    Doctor,
    Escalation,
    FeeScheduleItem,
    InsuranceEligibilityCheck,
    InsurancePolicy,
    PatientDocument,
    PatientProfile,
    Reminder,
    User,
    WorkflowRun,
)

ALL_TABLES = {
    "users",
    "patient_profiles",
    "departments",
    "doctors",
    "appointment_slots",
    "appointments",
    "patient_documents",
    "workflow_runs",
    "reminders",
    "escalations",
    "audit_events",
    "insurance_policies",
    "insurance_eligibility_checks",
    "fee_schedule_items",
    "billing_line_items",
    "billing_explanations",
}


def _uniq(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def make_user(db, email=None, role="patient"):
    user = User(
        email=email or f"{_uniq('user')}@example.test",
        hashed_password="hashed-password",
        full_name="CRUD User",
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_patient(db):
    user = make_user(db)
    profile = PatientProfile(
        user_id=user.id,
        date_of_birth=date(1990, 1, 1),
        gender="female",
        phone="+1 555 000 0000",
        preferred_language="en",
        contact_status="active",
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def make_department(db):
    dept = Department(name=_uniq("Dept"), code=_uniq("D"), description="Test department")
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


def make_doctor(db, department_id=None):
    if department_id is None:
        department_id = make_department(db).id
    doctor = Doctor(
        department_id=department_id,
        name="Dr. CRUD",
        specialty="General",
        license_number=_uniq("LIC"),
        email=f"{_uniq('doc')}@example.test",
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return doctor


def make_slot(db, doctor_id=None, when=None):
    if doctor_id is None:
        doctor_id = make_doctor(db).id
    start = when or datetime.now(timezone.utc) + timedelta(days=7)
    slot = AppointmentSlot(
        doctor_id=doctor_id, start_time=start, end_time=start + timedelta(hours=1)
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot


def make_appointment(db, patient_id=None, department_id=None, doctor_id=None):
    if patient_id is None:
        patient_id = make_patient(db).id
    if department_id is None:
        department_id = make_department(db).id
    if doctor_id is None:
        doctor_id = make_doctor(db, department_id).id
    appt = Appointment(
        patient_id=patient_id,
        department_id=department_id,
        doctor_id=doctor_id,
        status="requested",
        visit_type="consultation",
        reason="Test appointment",
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)
    return appt


# ── Schema sanity ─────────────────────────────────────────────────────────


def test_migrations_created_every_table(db_engine):
    tables = set(inspect(db_engine).get_table_names())
    missing = ALL_TABLES - tables
    assert not missing, f"Missing tables: {sorted(missing)}"


# ── Entity CRUD ───────────────────────────────────────────────────────────


def test_user_crud(db):
    user = make_user(db, email="crud.user@example.test")
    assert user.id and user.role == "patient"

    user.full_name = "Renamed User"
    user.role = "staff"
    db.commit()
    db.refresh(user)
    assert user.full_name == "Renamed User"
    assert user.role == "staff"

    db.delete(user)
    db.commit()
    assert db.get(User, user.id) is None


def test_patient_profile_crud(db):
    profile = make_patient(db)
    assert profile.id and profile.contact_status == "active"

    profile.preferred_language = "es"
    profile.contact_status = "contacted"
    db.commit()
    db.refresh(profile)
    assert profile.preferred_language == "es"
    assert profile.contact_status == "contacted"

    db.delete(profile)
    db.commit()
    assert db.get(PatientProfile, profile.id) is None


def test_department_crud(db):
    dept = make_department(db)
    assert dept.id and dept.is_active is True

    dept.name = "Renamed Department"
    dept.is_active = False
    db.commit()
    db.refresh(dept)
    assert dept.name == "Renamed Department"
    assert dept.is_active is False

    db.delete(dept)
    db.commit()
    assert db.get(Department, dept.id) is None


def test_doctor_crud(db):
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    assert doctor.id and doctor.department_id == dept.id

    doctor.specialty = "Interventional Cardiology"
    db.commit()
    db.refresh(doctor)
    assert doctor.specialty == "Interventional Cardiology"

    db.delete(doctor)
    db.commit()
    assert db.get(Doctor, doctor.id) is None


def test_appointment_slot_crud(db):
    slot = make_slot(db)
    assert slot.id and slot.is_booked is False

    slot.is_booked = True
    db.commit()
    db.refresh(slot)
    assert slot.is_booked is True

    db.delete(slot)
    db.commit()
    assert db.get(AppointmentSlot, slot.id) is None


def test_appointment_crud(db):
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)
    patient = make_patient(db)

    appt = Appointment(
        patient_id=patient.id,
        department_id=dept.id,
        doctor_id=doctor.id,
        slot_id=slot.id,
        status="scheduled",
        visit_type="follow_up",
        reason="Follow-up visit",
        scheduled_for=slot.start_time,
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)
    assert appt.id and appt.status == "scheduled"

    appt.status = "confirmed"
    appt.notes = "Bring records."
    db.commit()
    db.refresh(appt)
    assert appt.status == "confirmed"
    assert appt.notes == "Bring records."

    db.delete(appt)
    db.commit()
    assert db.get(Appointment, appt.id) is None


def test_patient_document_crud(db):
    patient = make_patient(db)
    doc = PatientDocument(
        patient_id=patient.id,
        filename="ecg.pdf",
        storage_path="/uploads/ecg.pdf",
        document_type="ecg",
        checksum=_uniq("chk"),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    assert doc.id and doc.is_duplicate is False

    doc.document_type = "lab_report"
    doc.is_duplicate = True
    db.commit()
    db.refresh(doc)
    assert doc.document_type == "lab_report"
    assert doc.is_duplicate is True

    db.delete(doc)
    db.commit()
    assert db.get(PatientDocument, doc.id) is None


def test_workflow_run_crud(db):
    patient = make_patient(db)
    run = WorkflowRun(
        patient_id=patient.id,
        request_text="I would like a cardiology follow-up appointment.",
        intent="book_appointment",
        status="running",
        current_step="routing",
        thread_id=_uniq("thread"),
        state={"route": "cardiology"},
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    assert run.id and run.status == "running"

    run.status = "completed"
    run.current_step = "follow_up_scheduled"
    run.state = {"route": "cardiology", "appointment_id": 7}
    db.commit()
    db.refresh(run)
    assert run.status == "completed"
    assert run.state["appointment_id"] == 7

    db.delete(run)
    db.commit()
    assert db.get(WorkflowRun, run.id) is None


def test_reminder_crud(db):
    patient = make_patient(db)
    appt = make_appointment(db, patient.id)
    reminder = Reminder(
        appointment_id=appt.id,
        patient_id=patient.id,
        reminder_type="appointment",
        scheduled_for=datetime.now(timezone.utc) + timedelta(days=1),
        channel="in_app",
        message="Reminder for your appointment.",
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    assert reminder.id and reminder.status == "pending"

    reminder.status = "sent"
    reminder.sent_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(reminder)
    assert reminder.status == "sent"
    assert reminder.sent_at is not None

    db.delete(reminder)
    db.commit()
    assert db.get(Reminder, reminder.id) is None


def test_escalation_crud(db):
    patient = make_patient(db)
    esc = Escalation(
        patient_id=patient.id,
        severity="high",
        reason="emergency language detected",
        details="Patient described acute symptoms.",
        status="open",
    )
    db.add(esc)
    db.commit()
    db.refresh(esc)
    assert esc.id and esc.status == "open"

    staff = make_user(db, email="crud.staff@example.test", role="staff")
    esc.status = "resolved"
    esc.reviewed_by = staff.id
    esc.resolved_at = datetime.now(timezone.utc)
    esc.resolution_notes = "Handled by staff."
    db.commit()
    db.refresh(esc)
    assert esc.status == "resolved"
    assert esc.reviewed_by == staff.id

    db.delete(esc)
    db.commit()
    assert db.get(Escalation, esc.id) is None


def test_audit_event_crud(db):
    user = make_user(db)
    event = AuditEvent(
        actor_user_id=user.id,
        action="appointment.booked",
        entity_type="Appointment",
        entity_id=1,
        details={"department": "Cardiology"},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    assert event.id and event.action == "appointment.booked"

    event.action = "appointment.rescheduled"
    event.details = {"slot_id": 5}
    db.commit()
    db.refresh(event)
    assert event.action == "appointment.rescheduled"
    assert event.details["slot_id"] == 5

    db.delete(event)
    db.commit()
    assert db.get(AuditEvent, event.id) is None


def test_insurance_policy_crud(db):
    patient = make_patient(db)
    policy = InsurancePolicy(
        patient_id=patient.id,
        provider_name="TestCare",
        policy_number=_uniq("POL"),
        plan_type="silver",
        active=True,
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    assert policy.id and policy.active is True

    policy.plan_type = "gold"
    policy.active = False
    db.commit()
    db.refresh(policy)
    assert policy.plan_type == "gold"
    assert policy.active is False

    db.delete(policy)
    db.commit()
    assert db.get(InsurancePolicy, policy.id) is None


def test_insurance_eligibility_check_crud(db):
    patient = make_patient(db)
    appt = make_appointment(db, patient.id)
    policy = InsurancePolicy(
        patient_id=patient.id,
        provider_name="TestCare",
        policy_number=_uniq("POL"),
        plan_type="silver",
        active=True,
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)

    check = InsuranceEligibilityCheck(
        appointment_id=appt.id,
        policy_id=policy.id,
        status="covered",
        coverage_summary="Coverage estimate.",
    )
    db.add(check)
    db.commit()
    db.refresh(check)
    assert check.id and check.status == "covered"

    check.status = "needs_pre_authorization"
    db.commit()
    db.refresh(check)
    assert check.status == "needs_pre_authorization"

    db.delete(check)
    db.commit()
    assert db.get(InsuranceEligibilityCheck, check.id) is None


def test_fee_schedule_item_crud(db):
    dept = make_department(db)
    item = FeeScheduleItem(
        department_id=dept.id,
        service_code=_uniq("SRV"),
        description="Cardiology consultation",
        amount_usd=Decimal("150.00"),
        category="consultation",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    assert item.id and item.amount_usd == Decimal("150.00")

    item.amount_usd = Decimal("165.50")
    item.is_active = False
    db.commit()
    db.refresh(item)
    assert item.amount_usd == Decimal("165.50")
    assert item.is_active is False

    db.delete(item)
    db.commit()
    assert db.get(FeeScheduleItem, item.id) is None


def test_billing_line_item_crud(db):
    patient = make_patient(db)
    appt = make_appointment(db, patient.id)
    item = BillingLineItem(
        appointment_id=appt.id,
        description="ECG interpretation",
        amount_usd=Decimal("85.00"),
        category="diagnostic",
        source="fee_schedule:CARD-ECG",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    assert item.id and item.source == "fee_schedule:CARD-ECG"

    item.amount_usd = Decimal("90.00")
    db.commit()
    db.refresh(item)
    assert item.amount_usd == Decimal("90.00")

    db.delete(item)
    db.commit()
    assert db.get(BillingLineItem, item.id) is None


def test_billing_explanation_crud(db):
    patient = make_patient(db)
    appt = make_appointment(db, patient.id)
    explanation = BillingExplanation(
        appointment_id=appt.id, summary_text="Estimate of expected charges."
    )
    db.add(explanation)
    db.commit()
    db.refresh(explanation)
    assert explanation.id and explanation.summary_text.startswith("Estimate")

    explanation.summary_text = "Updated estimate."
    db.commit()
    db.refresh(explanation)
    assert explanation.summary_text == "Updated estimate."

    db.delete(explanation)
    db.commit()
    assert db.get(BillingExplanation, explanation.id) is None


def test_delete_parent_cascades_to_dependent_rows(db):
    patient = make_patient(db)
    appt = make_appointment(db, patient.id)
    db.add(
        Reminder(
            appointment_id=appt.id,
            patient_id=patient.id,
            reminder_type="appointment",
            scheduled_for=datetime.now(timezone.utc) + timedelta(days=1),
        )
    )
    db.commit()

    db.delete(patient)
    db.commit()

    db.expire_all()
    assert db.scalar(select(func.count()).select_from(Appointment)) == 0
    assert db.scalar(select(func.count()).select_from(Reminder)) == 0
    assert db.scalar(select(func.count()).select_from(PatientProfile)) == 0
    assert db.scalar(select(func.count()).select_from(User)) == 1