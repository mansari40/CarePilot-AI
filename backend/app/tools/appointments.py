"""Appointment booking / rescheduling / cancellation tools.

Booking marks the slot unavailable with a guarded UPDATE so a slot can never be
double-booked; canceling frees the slot back up.
"""

from datetime import datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.models import Appointment, AppointmentSlot, Department, Doctor, PatientProfile
from app.tools.audit import log_audit
from app.tools.errors import (
    AppointmentNotFoundError,
    AppointmentNotActiveError,
    DepartmentNotFoundError,
    DoctorNotFoundError,
    PatientNotFoundError,
    SlotNotFoundError,
    SlotUnavailableError,
)


def _validate_patient(session: Session, patient_id: int) -> PatientProfile:
    patient = session.get(PatientProfile, patient_id)
    if patient is None:
        raise PatientNotFoundError(f"No patient profile with id {patient_id}")
    return patient


def _validate_department(session: Session, department_id: int) -> Department:
    department = session.get(Department, department_id)
    if department is None or not department.is_active:
        raise DepartmentNotFoundError(f"No active department with id {department_id}")
    return department


def _validate_doctor(session: Session, doctor_id: int, department_id: int) -> Doctor:
    doctor = session.get(Doctor, doctor_id)
    if doctor is None or not doctor.is_active:
        raise DoctorNotFoundError(f"No active doctor with id {doctor_id}")
    if doctor.department_id != department_id:
        raise DoctorNotFoundError(
            f"Doctor {doctor_id} does not belong to department {department_id}"
        )
    return doctor


def book_appointment(
    session: Session,
    patient_id: int,
    department_id: int,
    doctor_id: int,
    slot_id: int,
    visit_type: str = "consultation",
    reason: str | None = None,
    actor_user_id: int | None = None,
) -> Appointment:
    action = "appointment.booked"
    try:
        _validate_patient(session, patient_id)
        _validate_department(session, department_id)
        _validate_doctor(session, doctor_id, department_id)

        slot = session.get(AppointmentSlot, slot_id)
        if slot is None:
            raise SlotNotFoundError(f"No slot with id {slot_id}")
        if slot.doctor_id != doctor_id:
            raise SlotUnavailableError(
                f"Slot {slot_id} does not belong to doctor {doctor_id}"
            )

        claimed = session.execute(
            update(AppointmentSlot)
            .where(
                AppointmentSlot.id == slot_id,
                AppointmentSlot.is_booked.is_(False),
            )
            .values(is_booked=True)
            .returning(AppointmentSlot.id)
        ).first()
        if claimed is None:
            raise SlotUnavailableError(f"Slot {slot_id} is already booked")

        appointment = Appointment(
            patient_id=patient_id,
            department_id=department_id,
            doctor_id=doctor_id,
            slot_id=slot_id,
            status="scheduled",
            visit_type=visit_type,
            reason=reason,
            scheduled_for=slot.start_time,
        )
        session.add(appointment)
        session.flush()
        log_audit(
            session,
            action,
            "Appointment",
            entity_id=appointment.id,
            details={
                "patient_id": patient_id,
                "department_id": department_id,
                "doctor_id": doctor_id,
                "slot_id": slot_id,
                "visit_type": visit_type,
            },
            actor_user_id=actor_user_id,
        )
        session.commit()
        session.refresh(appointment)
        return appointment
    except Exception as exc:
        session.rollback()
        log_audit(
            session,
            f"{action}.failed",
            "Appointment",
            details={
                "patient_id": patient_id,
                "slot_id": slot_id,
                "reason": str(exc),
            },
            actor_user_id=actor_user_id,
        )
        session.commit()
        raise


def reschedule_appointment(
    session: Session,
    appointment_id: int,
    new_slot_id: int,
    actor_user_id: int | None = None,
) -> Appointment:
    action = "appointment.rescheduled"
    try:
        appointment = session.get(Appointment, appointment_id)
        if appointment is None:
            raise AppointmentNotFoundError(f"No appointment with id {appointment_id}")
        if appointment.status == "cancelled":
            raise AppointmentNotActiveError(
                f"Appointment {appointment_id} is cancelled and cannot be rescheduled"
            )

        new_slot = session.get(AppointmentSlot, new_slot_id)
        if new_slot is None:
            raise SlotNotFoundError(f"No slot with id {new_slot_id}")
        if new_slot.doctor_id != appointment.doctor_id:
            raise SlotUnavailableError(
                f"Slot {new_slot_id} does not belong to doctor {appointment.doctor_id}"
            )

        claimed = session.execute(
            update(AppointmentSlot)
            .where(
                AppointmentSlot.id == new_slot_id,
                AppointmentSlot.is_booked.is_(False),
            )
            .values(is_booked=True)
            .returning(AppointmentSlot.id)
        ).first()
        if claimed is None:
            raise SlotUnavailableError(f"Slot {new_slot_id} is already booked")

        old_slot_id = appointment.slot_id
        if old_slot_id is not None:
            old_slot = session.get(AppointmentSlot, old_slot_id)
            if old_slot is not None:
                old_slot.is_booked = False

        appointment.slot_id = new_slot_id
        appointment.scheduled_for = new_slot.start_time
        appointment.status = "rescheduled"
        session.flush()
        log_audit(
            session,
            action,
            "Appointment",
            entity_id=appointment.id,
            details={"old_slot_id": old_slot_id, "new_slot_id": new_slot_id},
            actor_user_id=actor_user_id,
        )
        session.commit()
        session.refresh(appointment)
        return appointment
    except Exception as exc:
        session.rollback()
        log_audit(
            session,
            f"{action}.failed",
            "Appointment",
            details={"appointment_id": appointment_id, "reason": str(exc)},
            actor_user_id=actor_user_id,
        )
        session.commit()
        raise


def cancel_appointment(
    session: Session,
    appointment_id: int,
    reason: str | None = None,
    actor_user_id: int | None = None,
) -> Appointment:
    action = "appointment.cancelled"
    try:
        appointment = session.get(Appointment, appointment_id)
        if appointment is None:
            raise AppointmentNotFoundError(f"No appointment with id {appointment_id}")
        if appointment.status == "cancelled":
            raise AppointmentNotActiveError(
                f"Appointment {appointment_id} is already cancelled"
            )

        slot_id = appointment.slot_id
        if slot_id is not None:
            slot = session.get(AppointmentSlot, slot_id)
            if slot is not None:
                slot.is_booked = False
            appointment.slot_id = None

        appointment.status = "cancelled"
        appointment.notes = reason or appointment.notes
        session.flush()
        log_audit(
            session,
            action,
            "Appointment",
            entity_id=appointment.id,
            details={"slot_id": slot_id, "reason": reason},
            actor_user_id=actor_user_id,
        )
        session.commit()
        session.refresh(appointment)
        return appointment
    except Exception as exc:
        session.rollback()
        log_audit(
            session,
            f"{action}.failed",
            "Appointment",
            details={"appointment_id": appointment_id, "reason": str(exc)},
            actor_user_id=actor_user_id,
        )
        session.commit()
        raise


def get_appointment(
    session: Session, appointment_id: int, actor_user_id: int | None = None
) -> Appointment:
    appointment = session.get(Appointment, appointment_id)
    if appointment is None:
        log_audit(
            session,
            "appointment.lookup.failed",
            "Appointment",
            details={"appointment_id": appointment_id, "reason": "not found"},
            actor_user_id=actor_user_id,
        )
        session.commit()
        raise AppointmentNotFoundError(f"No appointment with id {appointment_id}")
    log_audit(
        session,
        "appointment.lookup",
        "Appointment",
        entity_id=appointment.id,
        actor_user_id=actor_user_id,
    )
    session.commit()
    return appointment