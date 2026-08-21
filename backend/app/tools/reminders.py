"""Reminder tool — creates appointment reminders and follow-up tasks."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import Appointment, PatientProfile, Reminder
from app.tools.audit import log_audit
from app.tools.errors import AppointmentNotFoundError, PatientNotFoundError, ReminderValidationError


def create_reminder(
    session: Session,
    patient_id: int,
    reminder_type: str = "appointment",
    scheduled_for: datetime | None = None,
    appointment_id: int | None = None,
    channel: str = "in_app",
    message: str | None = None,
    actor_user_id: int | None = None,
) -> Reminder:
    action = "reminder.created"
    try:
        if session.get(PatientProfile, patient_id) is None:
            raise PatientNotFoundError(f"No patient profile with id {patient_id}")

        if appointment_id is not None:
            appointment = session.get(Appointment, appointment_id)
            if appointment is None:
                raise AppointmentNotFoundError(f"No appointment with id {appointment_id}")
            if appointment.patient_id != patient_id:
                raise ReminderValidationError(
                    f"Appointment {appointment_id} does not belong to patient {patient_id}"
                )

        if scheduled_for is None:
            if appointment_id is not None:
                appointment = session.get(Appointment, appointment_id)
                scheduled_for = appointment.scheduled_for or datetime.now()
            else:
                scheduled_for = datetime.now()
        if reminder_type not in ("appointment", "follow_up"):
            raise ReminderValidationError(f"Unknown reminder type: {reminder_type}")

        reminder = Reminder(
            appointment_id=appointment_id,
            patient_id=patient_id,
            reminder_type=reminder_type,
            scheduled_for=scheduled_for,
            channel=channel,
            message=message,
            status="pending",
        )
        session.add(reminder)
        session.flush()
        log_audit(
            session,
            action,
            "Reminder",
            entity_id=reminder.id,
            details={
                "appointment_id": appointment_id,
                "reminder_type": reminder_type,
                "scheduled_for": scheduled_for.isoformat(),
                "channel": channel,
            },
            actor_user_id=actor_user_id,
        )
        session.commit()
        session.refresh(reminder)
        return reminder
    except Exception as exc:
        session.rollback()
        log_audit(
            session,
            f"{action}.failed",
            "Reminder",
            details={"patient_id": patient_id, "reminder_type": reminder_type, "reason": str(exc)},
            actor_user_id=actor_user_id,
        )
        session.commit()
        raise