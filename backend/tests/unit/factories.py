"""Shared factories for tool tests."""

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select

from app.db.models import (
    AppointmentSlot,
    AuditEvent,
    Department,
    Doctor,
    FeeScheduleItem,
    PatientProfile,
    User,
)


def uniq(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def make_user(db, role="patient") -> User:
    user = User(
        email=f"{uniq('u')}@example.test",
        hashed_password="hash",
        full_name="Test User",
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_patient(db) -> PatientProfile:
    user = make_user(db)
    profile = PatientProfile(
        user_id=user.id,
        date_of_birth=date(1990, 1, 1),
        preferred_language="en",
        contact_status="active",
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def make_department(db, with_fees=True, name=None, code=None) -> Department:
    dept = Department(
        name=name or uniq("Dept"),
        code=code or uniq("D"),
        description="Test department",
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    if with_fees:
        db.add_all(
            [
                FeeScheduleItem(department_id=dept.id, service_code="CONS", description=f"{dept.name} consultation", amount_usd="120.00", category="consultation"),
                FeeScheduleItem(department_id=dept.id, service_code="FUP", description=f"{dept.name} follow-up visit", amount_usd="90.00", category="follow_up"),
                FeeScheduleItem(department_id=dept.id, service_code="PROC", description=f"{dept.name} procedure", amount_usd="300.00", category="procedure"),
                FeeScheduleItem(department_id=dept.id, service_code="FACILITY", description="Facility fee", amount_usd="40.00", category="facility"),
            ]
        )
        db.commit()
    return dept


def make_doctor(db, department_id=None) -> Doctor:
    if department_id is None:
        department_id = make_department(db).id
    doctor = Doctor(
        department_id=department_id,
        name="Dr. Test",
        specialty="General",
        license_number=uniq("LIC"),
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return doctor


def make_slot(db, doctor_id=None, day_offset=7, hour=9) -> AppointmentSlot:
    if doctor_id is None:
        doctor_id = make_doctor(db).id
    day = datetime.now(timezone.utc) + timedelta(days=day_offset)
    start = day.replace(hour=hour, minute=0, second=0, microsecond=0)
    slot = AppointmentSlot(
        doctor_id=doctor_id, start_time=start, end_time=start + timedelta(hours=1)
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot


def audit_count(db, action: str | None = None) -> int:
    query = select(func.count()).select_from(AuditEvent)
    if action:
        query = query.where(AuditEvent.action == action)
    return db.scalar(query)