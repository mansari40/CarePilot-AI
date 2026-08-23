"""Audit routes — list audit events (staff-only)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_staff
from app.db.models import AuditEvent, User
from app.schemas.escalation import AuditEventRead

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/", response_model=list[AuditEventRead])
def list_audit_events(
    staff: Annotated[User, Depends(require_staff)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 50,
) -> list[AuditEventRead]:
    events = (
        db.query(AuditEvent)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    return [AuditEventRead.model_validate(e) for e in events]
