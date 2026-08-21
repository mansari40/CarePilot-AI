"""Escalation routes — list and resolve (staff-only, records reviewed_by)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_staff
from app.db.models import Escalation, User
from app.schemas.escalation import EscalationRead, EscalationResolve
from app.tools.escalations import resolve_escalation

router = APIRouter(prefix="/api/escalations", tags=["escalations"])


@router.get("/", response_model=list[EscalationRead])
def list_escalations(
    staff: Annotated[User, Depends(require_staff)],
    db: Annotated[Session, Depends(get_db)],
) -> list[EscalationRead]:
    escalations = db.query(Escalation).order_by(Escalation.created_at.desc()).all()
    return [EscalationRead.model_validate(e) for e in escalations]


@router.get("/{escalation_id}", response_model=EscalationRead)
def read_escalation(
    escalation_id: int,
    staff: Annotated[User, Depends(require_staff)],
    db: Annotated[Session, Depends(get_db)],
) -> EscalationRead:
    esc = db.get(Escalation, escalation_id)
    if esc is None:
        raise HTTPException(status_code=404, detail="Escalation not found")
    return EscalationRead.model_validate(esc)


@router.post("/{escalation_id}/resolve", response_model=EscalationRead)
def resolve(
    escalation_id: int,
    payload: EscalationResolve,
    staff: Annotated[User, Depends(require_staff)],
    db: Annotated[Session, Depends(get_db)],
) -> EscalationRead:
    try:
        esc = resolve_escalation(
            db,
            escalation_id=escalation_id,
            reviewer_user_id=staff.id,
            resolution_notes=payload.resolution_notes,
            actor_user_id=staff.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return EscalationRead.model_validate(esc)
