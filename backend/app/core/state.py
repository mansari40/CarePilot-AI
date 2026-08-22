"""Shared graph state schema for AgentCare workflows.

``messages`` and ``tool_results`` use the ``add`` reducer so every node step
appends to the accumulated history, which the Postgres checkpointer persists
after every step.

Phase 4: the graph is split into specialist nodes (Safety & Escalation,
Department Routing, Appointment, Document, Follow-up).  The specialist
channels below (department_id, appointment_id, ...) are the coordination
contract between nodes: each node reads what it needs and writes its
outcome, and the conditional edges decide the next node.

Phase 6: Insurance Eligibility and Billing agents are inserted after
appointment booking and before the confirmation safety gate.

Phase 7: preferred_language is added so terminal nodes can produce
patient-facing text in the correct language.
"""

import operator
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage

RUN_STATUS_IN_PROGRESS = "in_progress"
RUN_STATUS_AWAITING_CONFIRMATION = "awaiting_confirmation"
RUN_STATUS_AWAITING_CLARIFICATION = "awaiting_clarification"
RUN_STATUS_AWAITING_DOCUMENT = "awaiting_document"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_ESCALATED = "escalated"

TERMINAL_STATUSES = {
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    RUN_STATUS_ESCALATED,
    RUN_STATUS_AWAITING_CONFIRMATION,
    RUN_STATUS_AWAITING_CLARIFICATION,
    RUN_STATUS_AWAITING_DOCUMENT,
}


class WorkflowState(TypedDict, total=False):
    """State shared by all graph nodes and persisted in the LangGraph checkpointer."""

    workflow_run_id: int
    patient_id: int
    request_text: str
    thread_id: str
    status: str
    current_step: str | None
    status_message: str | None
    failed_attempts: int
    turns: int
    messages: Annotated[list[AnyMessage], operator.add]
    tool_results: Annotated[list[dict[str, Any]], operator.add]

    # Phase 7: patient's preferred language for outgoing text.
    preferred_language: str

    # Safety & Escalation outcomes.
    safety_verdict: str | None  # "safe" | "escalate"
    safety_reason: str | None
    escalation_id: int | None
    escalation_reason: str | None

    # Department Routing outcomes.
    department_id: int | None
    department_name: str | None
    clarify_question: str | None

    # Coordination flags decided by routing, consumed by later nodes.
    needs_booking: bool
    needs_document: bool
    needs_reminder: bool

    # Appointment node outcome.
    appointment_id: int | None
    appointment_at: str | None

    # Document node outcome.
    document_id: int | None
    document_type: str | None
    missing_documents: list[str]

    # Follow-up node outcome.
    reminder_id: int | None

    # Insurance node outcome (Phase 6).
    insurance_check_id: int | None
    eligibility_status: str | None  # "covered" | "needs_preauthorization" | "not_covered" | "no_policy"

    # Billing node outcome (Phase 6).
    billing_explanation_id: int | None
    estimated_cost: str | None  # Decimal as string for JSON safety

    # Last node that finished its step via its completion tool.
    node_done: str | None

    # Final answer shown to the patient (built from real results only).
    final_response: str | None