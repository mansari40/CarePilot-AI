"""Tool tests: patient lookup, department lookup, slot availability, audit."""

import pytest

from app.tools.audit import log_audit
from app.tools.departments import find_department, get_department, list_departments
from app.tools.errors import DepartmentNotFoundError, DoctorNotFoundError, PatientNotFoundError
from app.tools.patients import find_patient_by_user_id, get_patient
from app.tools.slots import list_available_slots
from tests.unit.factories import (
    audit_count,
    make_department,
    make_doctor,
    make_patient,
    make_slot,
    make_user,
)
from app.db.models import AuditEvent
from datetime import datetime, timedelta, timezone


def test_patient_lookup_found_and_missing(db):
    patient = make_patient(db)
    found = find_patient_by_user_id(db, patient.user_id)
    assert found is not None and found.id == patient.id
    assert audit_count(db, "patient.lookup") == 1

    assert find_patient_by_user_id(db, 999999) is None

    with pytest.raises(PatientNotFoundError):
        get_patient(db, 999999)
    assert audit_count(db, "patient.lookup.failed") == 1


def test_department_lookup_by_name_and_code(db):
    dept = make_department(db, name="Cardiology", code="CARD")
    assert find_department(db, "cardiology").id == dept.id
    assert find_department(db, "CARD").id == dept.id
    assert find_department(db, "Oncology") is None
    assert audit_count(db, "department.lookup") == 3

    dept.is_active = False
    db.commit()
    assert find_department(db, "cardiology") is None

    with pytest.raises(DepartmentNotFoundError):
        get_department(db, 999999)
    assert audit_count(db, "department.lookup.failed") == 1

    listed = list_departments(db)
    assert all(d.is_active for d in listed)


def test_slot_availability_filters_and_empty(db):
    doctor = make_doctor(db)
    slot_a = make_slot(db, doctor.id, day_offset=7, hour=9)
    slot_b = make_slot(db, doctor.id, day_offset=7, hour=10)
    slot_b.is_booked = True
    db.commit()

    week = datetime.now(timezone.utc) + timedelta(days=7)
    available = list_available_slots(
        db, from_time=week.replace(hour=0, minute=0), to_time=week + timedelta(days=1)
    )
    assert [s.id for s in available] == [slot_a.id]

    filtered = list_available_slots(
        db,
        from_time=week.replace(hour=0, minute=0),
        to_time=week + timedelta(days=1),
        doctor_id=doctor.id,
    )
    assert [s.id for s in filtered] == [slot_a.id]

    empty = list_available_slots(
        db, from_time=week + timedelta(days=30), to_time=week + timedelta(days=31)
    )
    assert empty == []

    with pytest.raises(DoctorNotFoundError):
        list_available_slots(
            db, from_time=week, to_time=week + timedelta(days=1), doctor_id=999999
        )
    assert audit_count(db, "slot.availability.failed") == 1


def test_log_audit_writes_row(db):
    actor = make_user(db)
    event = log_audit(
        db,
        "test.action",
        "User",
        entity_id=1,
        details={"k": "v"},
        actor_user_id=actor.id,
    )
    db.commit()
    assert event.id is not None
    row = db.get(AuditEvent, event.id)
    assert row.action == "test.action"
    assert row.details == {"k": "v"}