"""Workflow run/run-resume endpoints (Phase 3/4, now with auth).

Patients: can only create runs for themselves and see their own runs.
Staff: can create runs for any patient and see all runs.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.orchestrator import resume_workflow, start_workflow
from app.core.persistence import get_workflow_run
from app.db.models import PatientProfile, User, WorkflowRun
from app.schemas.workflow import WorkflowResume, WorkflowRunCreate, WorkflowRunRead

from pydantic import BaseModel

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


def _get_patient_id_for_user(db: Session, user: User) -> int:
    """Return the patient profile id for the user. Raises 404 if not a patient profile."""
    if user.role == "patient":
        profile = (
            db.query(PatientProfile)
            .filter(PatientProfile.user_id == user.id)
            .first()
        )
        if profile is None:
            raise HTTPException(status_code=404, detail="Patient profile not found")
        return profile.id
    raise HTTPException(status_code=403, detail="Staff must use patient_id in request body")


def _check_run_access(db: Session, user: User, run: WorkflowRun) -> None:
    """Ensure the user can access this workflow run."""
    if user.role == "patient":
        profile = (
            db.query(PatientProfile)
            .filter(PatientProfile.user_id == user.id)
            .first()
        )
        if profile is None or run.patient_id != profile.id:
            raise HTTPException(status_code=403, detail="Access denied")


@router.get("/", response_model=list[WorkflowRunRead])
def list_runs(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 50,
) -> list[WorkflowRunRead]:
    """List workflow runs. Patients see only their own; staff see all."""
    q = db.query(WorkflowRun)
    if current_user.role == "patient":
        profile = (
            db.query(PatientProfile)
            .filter(PatientProfile.user_id == current_user.id)
            .first()
        )
        if profile is None:
            return []
        q = q.filter(WorkflowRun.patient_id == profile.id, WorkflowRun.hidden_from_patient.is_(False))
    runs = q.order_by(WorkflowRun.created_at.desc()).limit(limit).all()
    return [WorkflowRunRead.model_validate(r) for r in runs]


@router.post("/run", response_model=WorkflowRunRead, status_code=status.HTTP_201_CREATED)
def run_workflow(
    payload: WorkflowRunCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkflowRunRead:
    """Submit a plain-English request and run the multi-agent pipeline.

    Patients can only create runs for themselves. Staff can create for any patient.
    """
    if current_user.role == "patient":
        patient_id = _get_patient_id_for_user(db, current_user)
    else:
        patient_id = payload.patient_id

    run = start_workflow(patient_id, payload.request_text, payload.document_id)
    return WorkflowRunRead.model_validate(run)


@router.post("/{run_id}/resume", response_model=WorkflowRunRead)
def resume(
    payload: WorkflowResume,
    run_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkflowRunRead:
    """Resume a paused thread. Patients can only resume their own runs."""
    run = db.get(WorkflowRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No workflow run with id {run_id}")
    _check_run_access(db, current_user, run)
    resumed = resume_workflow(run_id, payload.message, payload.document_id)
    return WorkflowRunRead.model_validate(resumed)


@router.get("/{run_id}", response_model=WorkflowRunRead)
def get_run(
    run_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkflowRunRead:
    run = db.get(WorkflowRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No workflow run with id {run_id}")
    _check_run_access(db, current_user, run)
    return WorkflowRunRead.model_validate(run)


HIDEABLE_STATUSES = {"completed", "escalated", "failed", "cancelled"}


class HideRunPayload(BaseModel):
    hidden: bool = True


@router.patch("/{run_id}/hide", response_model=WorkflowRunRead)
def hide_run(
    run_id: int,
    payload: HideRunPayload,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkflowRunRead:
    """Soft-hide a workflow run from the patient's view. Only terminal states allowed."""
    run = db.get(WorkflowRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No workflow run with id {run_id}")
    _check_run_access(db, current_user, run)
    if payload.hidden and run.status not in HIDEABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot hide a request with status '{run.status}'. Only completed, escalated, failed, or cancelled requests can be removed from history.",
        )
    run.hidden_from_patient = payload.hidden
    db.commit()
    db.refresh(run)
    return WorkflowRunRead.model_validate(run)
