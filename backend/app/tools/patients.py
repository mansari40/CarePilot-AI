"""Patient registry tool — real lookups against patient_profiles/users."""

from sqlalchemy.orm import Session

from app.db.models import PatientProfile, User
from app.tools.audit import log_audit
from app.tools.errors import PatientNotFoundError


def find_patient_by_user_id(
    session: Session, user_id: int, actor_user_id: int | None = None
) -> PatientProfile | None:
    profile = (
        session.query(PatientProfile).filter(PatientProfile.user_id == user_id).first()
    )
    log_audit(
        session,
        "patient.lookup",
        "PatientProfile",
        entity_id=profile.id if profile else None,
        details={"user_id": user_id, "found": profile is not None},
        actor_user_id=actor_user_id,
    )
    session.commit()
    return profile


def get_patient(
    session: Session, patient_id: int, actor_user_id: int | None = None
) -> PatientProfile:
    profile = session.get(PatientProfile, patient_id)
    if profile is None:
        log_audit(
            session,
            "patient.lookup.failed",
            "PatientProfile",
            details={"patient_id": patient_id, "reason": "not found"},
            actor_user_id=actor_user_id,
        )
        session.commit()
        raise PatientNotFoundError(f"No patient profile with id {patient_id}")
    log_audit(
        session,
        "patient.lookup",
        "PatientProfile",
        entity_id=profile.id,
        actor_user_id=actor_user_id,
    )
    session.commit()
    return profile


def list_patients(
    session: Session, actor_user_id: int | None = None
) -> list[PatientProfile]:
    profiles = session.query(PatientProfile).order_by(PatientProfile.id).all()
    log_audit(
        session,
        "patient.list",
        "PatientProfile",
        details={"count": len(profiles)},
        actor_user_id=actor_user_id,
    )
    session.commit()
    return profiles


def find_user_by_email(session: Session, email: str) -> User | None:
    return session.query(User).filter(User.email == email.lower()).first()