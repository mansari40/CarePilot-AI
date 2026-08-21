"""Tool tests: booking marks a slot unavailable; cancel frees it; conflicts fail."""

import pytest

from app.tools.appointments import (
    book_appointment,
    cancel_appointment,
    get_appointment,
    reschedule_appointment,
)
from app.tools.errors import (
    AppointmentNotFoundError,
    AppointmentNotActiveError,
    DepartmentNotFoundError,
    DoctorNotFoundError,
    PatientNotFoundError,
    SlotUnavailableError,
)
from app.tools.slots import list_available_slots
from tests.unit.factories import (
    audit_count,
    make_department,
    make_doctor,
    make_patient,
    make_slot,
)
from datetime import timedelta


def test_booking_marks_slot_unavailable(db):
    patient = make_patient(db)
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)

    appt = book_appointment(
        db, patient.id, dept.id, doctor.id, slot.id, visit_type="consultation", reason="Annual checkup"
    )
    assert appt.status == "scheduled"
    assert appt.scheduled_for == slot.start_time
    db.refresh(slot)
    assert slot.is_booked is True

    booked = list_available_slots(
        db, from_time=slot.start_time - timedelta(hours=1), to_time=slot.start_time + timedelta(hours=2)
    )
    assert slot.id not in [s.id for s in booked]
    assert audit_count(db, "appointment.booked") == 1


def test_double_booking_same_slot_fails(db):
    patient = make_patient(db)
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)
    book_appointment(db, patient.id, dept.id, doctor.id, slot.id)

    other = make_patient(db)
    with pytest.raises(SlotUnavailableError):
        book_appointment(db, other.id, dept.id, doctor.id, slot.id)
    assert audit_count(db, "appointment.booked.failed") == 1


def test_booking_failures(db):
    patient = make_patient(db)
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)

    with pytest.raises(PatientNotFoundError):
        book_appointment(db, 999999, dept.id, doctor.id, slot.id)
    with pytest.raises(DepartmentNotFoundError):
        book_appointment(db, patient.id, 999999, doctor.id, slot.id)
    other_dept = make_department(db)
    with pytest.raises(DoctorNotFoundError):
        book_appointment(db, patient.id, other_dept.id, doctor.id, slot.id)
    assert audit_count(db, "appointment.booked.failed") == 3


def test_cancel_frees_slot_and_reschedule_swaps(db):
    patient = make_patient(db)
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id, day_offset=7, hour=9)
    slot2 = make_slot(db, doctor.id, day_offset=7, hour=11)

    appt = book_appointment(db, patient.id, dept.id, doctor.id, slot.id)
    cancelled = cancel_appointment(db, appt.id, reason="Patient rescheduling")
    assert cancelled.status == "cancelled"
    db.refresh(slot)
    assert slot.is_booked is False
    assert audit_count(db, "appointment.cancelled") == 1

    with pytest.raises(AppointmentNotActiveError):
        reschedule_appointment(db, appt.id, slot2.id)

    with pytest.raises(AppointmentNotActiveError):
        cancel_appointment(db, appt.id)

    appt2 = book_appointment(db, patient.id, dept.id, doctor.id, slot2.id)
    rescheduled = reschedule_appointment(db, appt2.id, slot.id)
    assert rescheduled.status == "rescheduled"
    assert rescheduled.slot_id == slot.id
    db.refresh(slot2)
    assert slot2.is_booked is False
    db.refresh(slot)
    assert slot.is_booked is True
    assert audit_count(db, "appointment.rescheduled") == 1


def test_reschedule_to_booked_slot_fails(db):
    patient = make_patient(db)
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot_a = make_slot(db, doctor.id, day_offset=8, hour=9)
    slot_b = make_slot(db, doctor.id, day_offset=8, hour=10)
    other = make_patient(db)
    book_appointment(db, other.id, dept.id, doctor.id, slot_b.id)

    appt = book_appointment(db, patient.id, dept.id, doctor.id, slot_a.id)
    with pytest.raises(SlotUnavailableError):
        reschedule_appointment(db, appt.id, slot_b.id)
    assert audit_count(db, "appointment.rescheduled.failed") == 1


def test_get_appointment(db):
    patient = make_patient(db)
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)
    appt = book_appointment(db, patient.id, dept.id, doctor.id, slot.id)
    assert get_appointment(db, appt.id).id == appt.id
    with pytest.raises(AppointmentNotFoundError):
        get_appointment(db, 999999)
    assert audit_count(db, "appointment.lookup.failed") == 1