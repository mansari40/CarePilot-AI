"""Persistence helpers for WorkflowRun rows.

The coordinator node writes the checkpoint's thread_id plus a human-readable
status/summary back onto the WorkflowRun row after every step.
"""

from datetime import datetime, timezone
from uuid import uuid4

from app.db.models import WorkflowRun
from app.db.session import SessionLocal


def create_workflow_run(patient_id: int, request_text: str) -> WorkflowRun:
    session = SessionLocal()
    try:
        run = WorkflowRun(
            patient_id=patient_id,
            request_text=request_text,
            status="pending",
            thread_id=uuid4().hex,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        return run
    finally:
        session.close()


def get_workflow_run(run_id: int) -> WorkflowRun | None:
    session = SessionLocal()
    try:
        return session.get(WorkflowRun, run_id)
    finally:
        session.close()


def update_workflow_run(
    run_id: int,
    *,
    thread_id: str | None = None,
    status: str | None = None,
    current_step: str | None = None,
    summary: str | None = None,
    state_payload: dict | None = None,
) -> None:
    session = SessionLocal()
    try:
        run = session.get(WorkflowRun, run_id)
        if run is None:
            return
        if thread_id is not None:
            run.thread_id = thread_id
        if status is not None:
            run.status = status
        if current_step is not None:
            run.current_step = current_step
        if summary is not None:
            run.summary = summary
        if state_payload is not None:
            run.state = state_payload
        session.commit()
    finally:
        session.close()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()