"""Audit logging tool — every tool call writes an AuditEvent through this helper."""

from sqlalchemy.orm import Session

from app.db.models import AuditEvent


def log_audit(
    session: Session,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    details: dict | None = None,
    actor_user_id: int | None = None,
    ip_address: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=ip_address,
    )
    session.add(event)
    return event