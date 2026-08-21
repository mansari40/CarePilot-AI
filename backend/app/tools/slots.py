"""Slot availability tool — real queries against appointment_slots."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import AppointmentSlot, Doctor
from app.tools.audit import log_audit
from app.tools.errors import DoctorNotFoundError


def list_available_slots(
    session: Session,
    from_time: datetime,
    to_time: datetime,
    doctor_id: int | None = None,
    department_id: int | None = None,
    actor_user_id: int | None = None,
) -> list[AppointmentSlot]:
    """Return unbooked slots in [from_time, to_time), optionally filtered."""
    query = session.query(AppointmentSlot).filter(
        AppointmentSlot.is_booked.is_(False),
        AppointmentSlot.start_time >= from_time,
        AppointmentSlot.start_time < to_time,
    )
    if doctor_id is not None:
        doctor = session.get(Doctor, doctor_id)
        if doctor is None:
            log_audit(
                session,
                "slot.availability.failed",
                "AppointmentSlot",
                details={"doctor_id": doctor_id, "reason": "doctor not found"},
                actor_user_id=actor_user_id,
            )
            session.commit()
            raise DoctorNotFoundError(f"No doctor with id {doctor_id}")
        query = query.filter(AppointmentSlot.doctor_id == doctor_id)
    if department_id is not None:
        query = query.join(Doctor, Doctor.id == AppointmentSlot.doctor_id).filter(
            Doctor.department_id == department_id
        )
    slots = query.order_by(AppointmentSlot.start_time).all()
    log_audit(
        session,
        "slot.availability",
        "AppointmentSlot",
        details={
            "count": len(slots),
            "doctor_id": doctor_id,
            "department_id": department_id,
            "from_time": from_time.isoformat(),
            "to_time": to_time.isoformat(),
        },
        actor_user_id=actor_user_id,
    )
    session.commit()
    return slots