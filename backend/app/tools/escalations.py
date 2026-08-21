"""Escalation tool — creates escalation records and resolves them with a reviewer."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import Escalation, PatientProfile, User, WorkflowRun
from app.tools.audit import log_audit
from app.tools.errors import (
    EscalationNotOpenError,
    PatientNotFoundError,
    WorkflowRunNotFoundError,
)


def create_escalation(
    session: Session,
    reason: str,
    severity: str = "medium",
    details: str | None = None,
    workflow_run_id: int | None = None,
    patient_id: int | None = None,
    actor_user_id: int | None = None,
) -> Escalation:
    action = "escalation.created"
    try:
        if workflow_run_id is not None and session.get(WorkflowRun, workflow_run_id) is None:
            raise WorkflowRunNotFoundError(f"No workflow run with id {workflow_run_id}")
        if patient_id is not None and session.get(PatientProfile, patient_id) is None:
            raise PatientNotFoundError(f"No patient profile with id {patient_id}")
        if severity not in ("low", "medium", "high", "critical"):
            raise ValueError(f"Unknown severity: {severity}")

        escalation = Escalation(
            workflow_run_id=workflow_run_id,
            patient_id=patient_id,
            severity=severity,
            reason=reason,
            details=details,
            status="open",
        )
        session.add(escalation)
        session.flush()
        log_audit(
            session,
            action,
            "Escalation",
            entity_id=escalation.id,
            details={"severity": severity, "workflow_run_id": workflow_run_id, "reason": reason},
            actor_user_id=actor_user_id,
        )
        session.commit()
        session.refresh(escalation)
        return escalation
    except Exception as exc:
        session.rollback()
        log_audit(
            session,
            f"{action}.failed",
            "Escalation",
            details={"reason": reason, "error": str(exc)},
            actor_user_id=actor_user_id,
        )
        session.commit()
        raise


def resolve_escalation(
    session: Session,
    escalation_id: int,
    reviewer_user_id: int,
    resolution_notes: str,
    actor_user_id: int | None = None,
) -> Escalation:
    action = "escalation.resolved"
    try:
        escalation = session.get(Escalation, escalation_id)
        if escalation is None:
            raise EscalationNotOpenError(f"No escalation with id {escalation_id}")
        if escalation.status != "open":
            raise EscalationNotOpenError(
                f"Escalation {escalation_id} is not open (status={escalation.status})"
            )
        reviewer = session.get(User, reviewer_user_id)
        if reviewer is None or reviewer.role != "staff":
            raise ValueError("Reviewer must be a staff user")

        escalation.status = "resolved"
        escalation.reviewed_by = reviewer_user_id
        escalation.resolved_at = datetime.now()
        escalation.resolution_notes = resolution_notes
        session.flush()
        log_audit(
            session,
            action,
            "Escalation",
            entity_id=escalation.id,
            details={"reviewed_by": reviewer_user_id},
            actor_user_id=actor_user_id,
        )
        session.commit()
        session.refresh(escalation)
        return escalation
    except Exception as exc:
        session.rollback()
        log_audit(
            session,
            f"{action}.failed",
            "Escalation",
            details={"escalation_id": escalation_id, "reason": str(exc)},
            actor_user_id=actor_user_id,
        )
        session.commit()
        raise