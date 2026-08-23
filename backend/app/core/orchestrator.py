"""Workflow orchestration: start a new thread or resume an existing one.

Start: create a WorkflowRun row (thread_id assigned), open a LangGraph thread
on the Postgres checkpointer, and run the pipeline from the Safety entry
screen until it pauses or ends.

Resume: reopen the same thread via the checkpointer with the accumulated
state and re-enter the graph at the node that follows the paused terminal —
determined by the run's status:

* ``awaiting_confirmation``  -> the booking is confirmed, continue with
  documents (``document_ingest``).
* ``awaiting_clarification`` -> the patient answered the routing question,
  re-run department routing with the answer.
* ``awaiting_document``      -> the patient supplied the missing document,
  re-run the document step with the uploaded ``document_id``.

``update_state(as_node=...)`` marks the target node as the pending task so
``invoke(None)`` runs exactly that node — the side-effecting booking node is
never re-entered on resume.

Phase 7: Incoming non-English requests are translated to English before the
graph.  Outgoing patient-facing text (final_response) is translated back into
the patient's preferred_language after the graph completes.
"""

from langchain_core.messages import HumanMessage

from app.core.graph import get_graph
from app.core.persistence import create_workflow_run, get_workflow_run, update_workflow_run
from app.core.state import (
    RUN_STATUS_AWAITING_CLARIFICATION,
    RUN_STATUS_AWAITING_CONFIRMATION,
    RUN_STATUS_AWAITING_DOCUMENT,
    RUN_STATUS_IN_PROGRESS,
)
from app.db.models import PatientProfile, WorkflowRun
from app.services.translation import (
    detect_language,
    translate_from_english,
    translate_to_english,
)

_NODE_BOOK_APPOINTMENT = "book_appointment"
_NODE_DOCUMENT_INGEST = "document_ingest"
_NODE_ROUTE_DEPARTMENT = "route_department"


def _config(run: WorkflowRun) -> dict:
    return {"configurable": {"thread_id": run.thread_id}}


def _resume_node(status: str) -> str:
    """The node to re-enter after a paused terminal, given the run status."""
    if status == RUN_STATUS_AWAITING_CONFIRMATION:
        return _NODE_DOCUMENT_INGEST
    if status == RUN_STATUS_AWAITING_CLARIFICATION:
        return _NODE_ROUTE_DEPARTMENT
    if status == RUN_STATUS_AWAITING_DOCUMENT:
        return _NODE_DOCUMENT_INGEST
    raise ValueError(f"Cannot resume a run in status '{status}'")


def _get_preferred_language(patient_id: int) -> str:
    """Look up the patient's preferred_language from the database."""
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        profile = session.get(PatientProfile, patient_id)
        if profile is not None:
            return profile.preferred_language or "en"
    except Exception:  # noqa: BLE001
        pass
    finally:
        session.close()
    return "en"


def start_workflow(
    patient_id: int, request_text: str, document_id: int | None = None
) -> WorkflowRun:
    """Create a WorkflowRun row and run the pipeline from the safety screen."""
    # Phase 7: detect language and translate incoming request to English.
    source_lang = detect_language(request_text)
    english_text = translate_to_english(request_text, source_lang)
    preferred_language = _get_preferred_language(patient_id)

    run = create_workflow_run(patient_id, english_text)
    try:
        graph = get_graph()
        graph.invoke(
            {
                "workflow_run_id": run.id,
                "patient_id": patient_id,
                "request_text": english_text,
                "thread_id": run.thread_id,
                "status": RUN_STATUS_IN_PROGRESS,
                "failed_attempts": 0,
                "needs_booking": False,
                "needs_document": False,
                "needs_reminder": False,
                "missing_documents": [],
                "messages": [HumanMessage(content=english_text)],
                "tool_results": [],
                "preferred_language": preferred_language,
                **({"document_id": document_id} if document_id is not None else {}),
            },
            _config(run),
        )
    except Exception as exc:
        update_workflow_run(
            run.id,
            status="failed",
            state_payload={"error": str(exc)},
        )
        return get_workflow_run(run.id)  # type: ignore[return-value]

    # Phase 7: translate outgoing final_response back to preferred language.
    refreshed = get_workflow_run(run.id)
    if refreshed is not None and refreshed.state.get("final_response"):
        if preferred_language != "en":
            translated = translate_from_english(
                refreshed.state["final_response"], preferred_language
            )
            update_workflow_run(
                run.id,
                state_payload={
                    **refreshed.state,
                    "final_response": translated,
                },
            )
            refreshed = get_workflow_run(run.id)
    return refreshed  # type: ignore[return-value]


def resume_workflow(
    run_id: int, message: str, document_id: int | None = None
) -> WorkflowRun:
    """Resume an existing thread with new input from the patient/staff."""
    run = get_workflow_run(run_id)
    if run is None or run.thread_id is None:
        raise ValueError(f"No workflow run with id {run_id}")
    node = _resume_node(run.status)

    # Phase 7: detect language and translate incoming message to English.
    source_lang = detect_language(message)
    english_text = translate_to_english(message, source_lang)

    graph = get_graph()
    updates: dict = {
        "messages": [HumanMessage(content=english_text)],
        "status": RUN_STATUS_IN_PROGRESS,
        "turns": 0,
        "failed_attempts": 0,
    }
    if run.status == RUN_STATUS_AWAITING_CLARIFICATION:
        updates["clarify_question"] = None
    if run.status == RUN_STATUS_AWAITING_DOCUMENT:
        updates["missing_documents"] = []
    if document_id is not None:
        updates["document_id"] = document_id
    graph.update_state(_config(run), updates, as_node=node)
    try:
        graph.invoke(None, _config(run))
    except Exception as exc:
        update_workflow_run(
            run.id,
            status="failed",
            state_payload={**(run.state or {}), "error": str(exc)},
        )
        return get_workflow_run(run.id)  # type: ignore[return-value]

    # Phase 7: translate outgoing final_response back to preferred language.
    refreshed = get_workflow_run(run.id)
    if refreshed is not None and refreshed.state.get("final_response"):
        preferred_language = _get_preferred_language(refreshed.patient_id)
        if preferred_language != "en":
            translated = translate_from_english(
                refreshed.state["final_response"], preferred_language
            )
            update_workflow_run(
                run.id,
                state_payload={
                    **refreshed.state,
                    "final_response": translated,
                },
            )
            refreshed = get_workflow_run(run.id)
    return refreshed  # type: ignore[return-value]
