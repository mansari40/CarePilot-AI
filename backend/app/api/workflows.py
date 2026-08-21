"""Workflow run/run-resume endpoints (Phase 3)."""

from fastapi import APIRouter, HTTPException

from app.core.orchestrator import resume_workflow, start_workflow
from app.core.persistence import get_workflow_run
from app.schemas.workflow import WorkflowResume, WorkflowRunCreate, WorkflowRunRead

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.post("/run", response_model=WorkflowRunRead)
def run_workflow(payload: WorkflowRunCreate) -> WorkflowRunRead:
    """Submit a plain-English request and run the multi-agent pipeline."""
    run = start_workflow(payload.patient_id, payload.request_text, payload.document_id)
    return WorkflowRunRead.model_validate(run)


@router.post("/{run_id}/resume", response_model=WorkflowRunRead)
def resume(payload: WorkflowResume, run_id: int) -> WorkflowRunRead:
    """Resume a paused thread with new input (confirmation, clarification answer, document)."""
    run = get_workflow_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No workflow run with id {run_id}")
    resumed = resume_workflow(run_id, payload.message, payload.document_id)
    return WorkflowRunRead.model_validate(resumed)


@router.get("/{run_id}", response_model=WorkflowRunRead)
def get_run(run_id: int) -> WorkflowRunRead:
    run = get_workflow_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No workflow run with id {run_id}")
    return WorkflowRunRead.model_validate(run)