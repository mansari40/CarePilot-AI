"""Analytics service — real aggregation queries over persisted data."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, case, extract, literal_column
from sqlalchemy.orm import Session

from app.db.models import (
    Appointment,
    Department,
    Doctor,
    Escalation,
    InsuranceEligibilityCheck,
    PatientDocument,
    PatientProfile,
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def appointments_by_department(db: Session) -> list[dict]:
    rows = (
        db.query(
            Department.name.label("department"),
            func.count(Appointment.id).label("count"),
        )
        .join(Appointment, Appointment.department_id == Department.id, isouter=True)
        .group_by(Department.name)
        .order_by(Department.name)
        .all()
    )
    return [{"department": r.department, "count": r.count} for r in rows]


def appointments_by_status(db: Session) -> list[dict]:
    rows = (
        db.query(
            Appointment.status.label("status"),
            func.count(Appointment.id).label("count"),
        )
        .group_by(Appointment.status)
        .order_by(Appointment.status)
        .all()
    )
    return [{"status": r.status, "count": r.count} for r in rows]


def avg_request_to_booking_minutes(db: Session) -> dict:
    """Average time from workflow created_at to appointment created_at for booked appts."""
    result = (
        db.query(
            func.avg(
                func.extract("epoch", Appointment.created_at - func.coalesce(Appointment.scheduled_for, Appointment.created_at))
            )
        )
        .filter(Appointment.status.in_(["booked", "confirmed"]))
        .scalar()
    )
    if result is None:
        return {"average_seconds": 0.0, "sample_count": 0}
    return {"average_seconds": round(float(result), 1), "sample_count": _count_booked(db)}


def _count_booked(db: Session) -> int:
    return (
        db.query(func.count(Appointment.id))
        .filter(Appointment.status.in_(["booked", "confirmed"]))
        .scalar()
        or 0
    )


def document_completion_rate(db: Session) -> dict:
    total_appts = db.query(func.count(Appointment.id)).scalar() or 0
    appts_with_docs = (
        db.query(func.count(func.distinct(PatientDocument.appointment_id)))
        .filter(PatientDocument.appointment_id.isnot(None))
        .scalar()
        or 0
    )
    total_docs = db.query(func.count(PatientDocument.id)).scalar() or 0
    duplicates = (
        db.query(func.count(PatientDocument.id))
        .filter(PatientDocument.is_duplicate.is_(True))
        .scalar()
        or 0
    )
    return {
        "total_appointments": total_appts,
        "appointments_with_documents": appts_with_docs,
        "completion_rate_pct": round(appts_with_docs / total_appts * 100, 1) if total_appts else 0.0,
        "total_documents": total_docs,
        "duplicate_documents": duplicates,
        "duplicate_rate_pct": round(duplicates / total_docs * 100, 1) if total_docs else 0.0,
    }


def escalation_stats(db: Session) -> dict:
    total = db.query(func.count(Escalation.id)).scalar() or 0
    open_count = (
        db.query(func.count(Escalation.id))
        .filter(Escalation.status == "open")
        .scalar()
        or 0
    )
    resolved = (
        db.query(func.count(Escalation.id))
        .filter(Escalation.status == "resolved")
        .scalar()
        or 0
    )
    avg_resolution = (
        db.query(
            func.avg(
                func.extract("epoch", Escalation.resolved_at - Escalation.created_at)
            )
        )
        .filter(Escalation.resolved_at.isnot(None))
        .scalar()
    )
    by_severity = (
        db.query(
            Escalation.severity.label("severity"),
            func.count(Escalation.id).label("count"),
        )
        .group_by(Escalation.severity)
        .order_by(Escalation.severity)
        .all()
    )
    return {
        "total": total,
        "open": open_count,
        "resolved": resolved,
        "avg_resolution_seconds": round(float(avg_resolution), 1) if avg_resolution else 0.0,
        "by_severity": [{"severity": r.severity, "count": r.count} for r in by_severity],
    }


def insurance_eligibility_outcomes(db: Session) -> list[dict]:
    rows = (
        db.query(
            InsuranceEligibilityCheck.status.label("status"),
            func.count(InsuranceEligibilityCheck.id).label("count"),
        )
        .group_by(InsuranceEligibilityCheck.status)
        .order_by(InsuranceEligibilityCheck.status)
        .all()
    )
    return [{"status": r.status, "count": r.count} for r in rows]


def busiest_doctors(db: Session, limit: int = 5) -> list[dict]:
    rows = (
        db.query(
            Doctor.name.label("doctor"),
            Department.name.label("department"),
            func.count(Appointment.id).label("appointment_count"),
        )
        .join(Appointment, Appointment.doctor_id == Doctor.id, isouter=True)
        .join(Department, Doctor.department_id == Department.id)
        .group_by(Doctor.name, Department.name)
        .order_by(func.count(Appointment.id).desc())
        .limit(limit)
        .all()
    )
    return [
        {"doctor": r.doctor, "department": r.department, "appointment_count": r.appointment_count}
        for r in rows
    ]


def busiest_slots(db: Session, limit: int = 5) -> list[dict]:
    day_expr = func.date_trunc("day", Appointment.scheduled_for).label("day")
    rows = (
        db.query(
            day_expr,
            func.count(Appointment.id).label("count"),
        )
        .filter(Appointment.scheduled_for.isnot(None))
        .group_by(literal_column("day"))
        .order_by(func.count(Appointment.id).desc())
        .limit(limit)
        .all()
    )
    return [
        {"day": r.day.isoformat() if r.day else None, "count": r.count}
        for r in rows
    ]


def get_dashboard(db: Session) -> dict:
    return {
        "appointments_by_department": appointments_by_department(db),
        "appointments_by_status": appointments_by_status(db),
        "avg_request_to_booking": avg_request_to_booking_minutes(db),
        "document_completion": document_completion_rate(db),
        "escalation_stats": escalation_stats(db),
        "insurance_eligibility_outcomes": insurance_eligibility_outcomes(db),
        "busiest_doctors": busiest_doctors(db),
        "busiest_days": busiest_slots(db),
    }
