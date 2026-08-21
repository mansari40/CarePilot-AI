"""Department lookup tool — real lookups against departments."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Department
from app.tools.audit import log_audit
from app.tools.errors import DepartmentNotFoundError


def find_department(
    session: Session, query: str, actor_user_id: int | None = None
) -> Department | None:
    """Match a department by name or code, case-insensitively."""
    q = query.strip().lower()
    dept = (
        session.query(Department)
        .filter(
            func.lower(Department.name) == q,
            Department.is_active.is_(True),
        )
        .first()
    )
    if dept is None:
        dept = (
            session.query(Department)
            .filter(
                func.lower(Department.code) == q,
                Department.is_active.is_(True),
            )
            .first()
        )
    log_audit(
        session,
        "department.lookup",
        "Department",
        entity_id=dept.id if dept else None,
        details={"query": query, "found": dept is not None},
        actor_user_id=actor_user_id,
    )
    session.commit()
    return dept


def get_department(
    session: Session, department_id: int, actor_user_id: int | None = None
) -> Department:
    dept = session.get(Department, department_id)
    if dept is None:
        log_audit(
            session,
            "department.lookup.failed",
            "Department",
            details={"department_id": department_id, "reason": "not found"},
            actor_user_id=actor_user_id,
        )
        session.commit()
        raise DepartmentNotFoundError(f"No department with id {department_id}")
    log_audit(
        session,
        "department.lookup",
        "Department",
        entity_id=dept.id,
        actor_user_id=actor_user_id,
    )
    session.commit()
    return dept


def list_departments(
    session: Session, active_only: bool = True, actor_user_id: int | None = None
) -> list[Department]:
    query = session.query(Department).order_by(Department.name)
    if active_only:
        query = query.filter(Department.is_active.is_(True))
    departments = query.all()
    log_audit(
        session,
        "department.list",
        "Department",
        details={"count": len(departments), "active_only": active_only},
        actor_user_id=actor_user_id,
    )
    session.commit()
    return departments