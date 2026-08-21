"""LangGraph StateGraph with the Postgres checkpointer.

Phase 4: the graph is a pipeline of specialist agents instead of one
Coordinator:

    safety_screen -> route_department -> book_appointment -> insurance_check
                                                           -> billing_generate
                                                           -> safety_before_confirm
                                                          -> wait_confirm (END)
       |                       |-> safety_before_clarify -> clarify (END)
       |                       `-> document_ingest -> safety_before_doc -> needs_document (END)
       |                                          `-> followup -> safety_before_respond -> respond (END)
       `-> escalate (END)

Phase 6: Insurance Eligibility and Billing agents are inserted between
appointment booking and the confirmation safety gate.

* Every agent keeps looping on itself (conditional self-edge) until its
  completion tool is called, so the checkpointer persists the accumulated
  state after every single step (what makes restart-and-resume work).
* The Safety & Escalation node runs once on every incoming request (entry)
  and again before every patient-facing terminal (gates); anything unsafe
  routes to the ``escalate`` terminal from anywhere in the graph.
* Terminals ``clarify``, ``needs_document`` and ``wait_confirm`` are resume
  points: ``orchestrator.resume_workflow`` re-enters the graph at the
  appropriate node via ``update_state(as_node=...)``.
"""

from functools import lru_cache
from threading import Lock

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import get_settings
from app.core.nodes import (
    NODE_BOOK_APPOINTMENT,
    NODE_CLARIFY,
    NODE_DOCUMENT_INGEST,
    NODE_ESCALATE,
    NODE_FOLLOWUP,
    NODE_INSURANCE_CHECK,
    NODE_BILLING_GENERATE,
    NODE_NEEDS_DOCUMENT,
    NODE_RESPOND,
    NODE_ROUTE_DEPARTMENT,
    NODE_SAFETY_BEFORE_CLARIFY,
    NODE_SAFETY_BEFORE_CONFIRM,
    NODE_SAFETY_BEFORE_DOC,
    NODE_SAFETY_BEFORE_RESPOND,
    NODE_SAFETY_SCREEN,
    NODE_WAIT_CONFIRM,
    AppointmentAgentNode,
    BillingAgentNode,
    DocumentAgentNode,
    FollowupAgentNode,
    InsuranceAgentNode,
    RoutingAgentNode,
    SafetyAgentNode,
    TerminalNode,
    build_terminals,
)
from app.core.state import WorkflowState
from app.core.tools import (
    APPOINTMENT_TOOLS,
    BILLING_TOOLS,
    DOCUMENT_TOOLS,
    FOLLOWUP_TOOLS,
    INSURANCE_TOOLS,
    ROUTING_TOOLS,
    SAFETY_TOOLS,
)

_pool: ConnectionPool | None = None
_saver: PostgresSaver | None = None
_pool_lock = Lock()


def _dsn() -> str:
    """PostgresSaver wants a plain libpq DSN (no SQLAlchemy '+psycopg' suffix)."""
    return get_settings().database_url.replace("postgresql+psycopg://", "postgresql://")


def get_checkpointer() -> PostgresSaver:
    """Process-wide PostgresSaver backed by a connection pool."""
    global _pool, _saver
    with _pool_lock:
        if _saver is None:
            pool = ConnectionPool(
                _dsn(),
                min_size=1,
                max_size=4,
                open=True,
                kwargs={
                    "autocommit": True,
                    "prepare_threshold": 0,
                    "row_factory": dict_row,
                },
            )
            pool.open()
            saver = PostgresSaver(pool)
            saver.setup()
            _pool = pool
            _saver = saver
        return _saver


def _must_escalate(state: WorkflowState) -> bool:
    return bool(state.get("escalation_id") or state.get("safety_verdict") == "escalate")


def _route_safety_screen(state: WorkflowState) -> str:
    if state.get("status") == "failed":
        return END
    if _must_escalate(state):
        return NODE_ESCALATE
    if state.get("safety_verdict") == "safe":
        return NODE_ROUTE_DEPARTMENT
    return NODE_SAFETY_SCREEN


def _route_routing(state: WorkflowState) -> str:
    if state.get("status") == "failed":
        return END
    if _must_escalate(state):
        return NODE_ESCALATE
    if state.get("clarify_question"):
        return NODE_SAFETY_BEFORE_CLARIFY
    if state.get("department_id"):
        return NODE_BOOK_APPOINTMENT if state.get("needs_booking") else NODE_DOCUMENT_INGEST
    return NODE_ROUTE_DEPARTMENT


def _route_appointment(state: WorkflowState) -> str:
    if state.get("status") == "failed":
        return END
    if _must_escalate(state):
        return NODE_ESCALATE
    if state.get("appointment_id"):
        return NODE_INSURANCE_CHECK
    if state.get("node_done") == NODE_BOOK_APPOINTMENT:
        return NODE_DOCUMENT_INGEST
    return NODE_BOOK_APPOINTMENT


def _route_insurance(state: WorkflowState) -> str:
    if state.get("status") == "failed":
        return END
    if _must_escalate(state):
        return NODE_ESCALATE
    if state.get("node_done") == NODE_INSURANCE_CHECK:
        return NODE_BILLING_GENERATE
    return NODE_INSURANCE_CHECK


def _route_billing(state: WorkflowState) -> str:
    if state.get("status") == "failed":
        return END
    if _must_escalate(state):
        return NODE_ESCALATE
    if state.get("node_done") == NODE_BILLING_GENERATE:
        return NODE_SAFETY_BEFORE_CONFIRM
    return NODE_BILLING_GENERATE


def _route_document(state: WorkflowState) -> str:
    if state.get("status") == "failed":
        return END
    if _must_escalate(state):
        return NODE_ESCALATE
    if state.get("missing_documents"):
        return NODE_SAFETY_BEFORE_DOC
    if state.get("node_done") == NODE_DOCUMENT_INGEST:
        return NODE_FOLLOWUP
    return NODE_DOCUMENT_INGEST


def _route_followup(state: WorkflowState) -> str:
    if state.get("status") == "failed":
        return END
    if _must_escalate(state):
        return NODE_ESCALATE
    if state.get("node_done") == NODE_FOLLOWUP:
        return NODE_SAFETY_BEFORE_RESPOND
    return NODE_FOLLOWUP


def _gate_route(target: str):
    def _route(state: WorkflowState) -> str:
        if state.get("status") == "failed":
            return END
        if _must_escalate(state):
            return NODE_ESCALATE
        return target

    return _route


def build_graph(overrides: dict | None = None) -> StateGraph:
    """Build the compiled graph with the Phase 4 specialist nodes.

    ``overrides`` maps node names to custom node instances (used by tests).
    """
    overrides = overrides or {}
    terminals: dict[str, TerminalNode] = build_terminals()

    def _node(key: str, default):
        return overrides.get(key, default)

    builder = StateGraph(WorkflowState)

    builder.add_node(
        NODE_SAFETY_SCREEN,
        _node(
            NODE_SAFETY_SCREEN,
            SafetyAgentNode(tool_specs=SAFETY_TOOLS, gate=False),
        ),
    )
    builder.add_node(
        NODE_ROUTE_DEPARTMENT,
        _node(NODE_ROUTE_DEPARTMENT, RoutingAgentNode(tool_specs=ROUTING_TOOLS)),
    )
    builder.add_node(
        NODE_BOOK_APPOINTMENT,
        _node(NODE_BOOK_APPOINTMENT, AppointmentAgentNode(tool_specs=APPOINTMENT_TOOLS)),
    )
    builder.add_node(
        NODE_INSURANCE_CHECK,
        _node(NODE_INSURANCE_CHECK, InsuranceAgentNode(tool_specs=INSURANCE_TOOLS)),
    )
    builder.add_node(
        NODE_BILLING_GENERATE,
        _node(NODE_BILLING_GENERATE, BillingAgentNode(tool_specs=BILLING_TOOLS)),
    )
    builder.add_node(
        NODE_DOCUMENT_INGEST,
        _node(NODE_DOCUMENT_INGEST, DocumentAgentNode(tool_specs=DOCUMENT_TOOLS)),
    )
    builder.add_node(
        NODE_FOLLOWUP,
        _node(NODE_FOLLOWUP, FollowupAgentNode(tool_specs=FOLLOWUP_TOOLS)),
    )

    for gate_name in (
        NODE_SAFETY_BEFORE_CLARIFY,
        NODE_SAFETY_BEFORE_CONFIRM,
        NODE_SAFETY_BEFORE_DOC,
        NODE_SAFETY_BEFORE_RESPOND,
    ):
        builder.add_node(
            gate_name,
            _node(gate_name, SafetyAgentNode(tool_specs=SAFETY_TOOLS, gate=True)),
        )

    for name, terminal in terminals.items():
        builder.add_node(name, _node(name, terminal))

    builder.add_edge(START, NODE_SAFETY_SCREEN)
    builder.add_conditional_edges(
        NODE_SAFETY_SCREEN,
        _route_safety_screen,
        {
            NODE_SAFETY_SCREEN: NODE_SAFETY_SCREEN,
            NODE_ROUTE_DEPARTMENT: NODE_ROUTE_DEPARTMENT,
            NODE_ESCALATE: NODE_ESCALATE,
            END: END,
        },
    )
    builder.add_conditional_edges(
        NODE_ROUTE_DEPARTMENT,
        _route_routing,
        {
            NODE_ROUTE_DEPARTMENT: NODE_ROUTE_DEPARTMENT,
            NODE_BOOK_APPOINTMENT: NODE_BOOK_APPOINTMENT,
            NODE_DOCUMENT_INGEST: NODE_DOCUMENT_INGEST,
            NODE_SAFETY_BEFORE_CLARIFY: NODE_SAFETY_BEFORE_CLARIFY,
            NODE_ESCALATE: NODE_ESCALATE,
            END: END,
        },
    )
    builder.add_conditional_edges(
        NODE_BOOK_APPOINTMENT,
        _route_appointment,
        {
            NODE_BOOK_APPOINTMENT: NODE_BOOK_APPOINTMENT,
            NODE_DOCUMENT_INGEST: NODE_DOCUMENT_INGEST,
            NODE_INSURANCE_CHECK: NODE_INSURANCE_CHECK,
            NODE_ESCALATE: NODE_ESCALATE,
            END: END,
        },
    )
    builder.add_conditional_edges(
        NODE_INSURANCE_CHECK,
        _route_insurance,
        {
            NODE_INSURANCE_CHECK: NODE_INSURANCE_CHECK,
            NODE_BILLING_GENERATE: NODE_BILLING_GENERATE,
            NODE_ESCALATE: NODE_ESCALATE,
            END: END,
        },
    )
    builder.add_conditional_edges(
        NODE_BILLING_GENERATE,
        _route_billing,
        {
            NODE_BILLING_GENERATE: NODE_BILLING_GENERATE,
            NODE_SAFETY_BEFORE_CONFIRM: NODE_SAFETY_BEFORE_CONFIRM,
            NODE_ESCALATE: NODE_ESCALATE,
            END: END,
        },
    )
    builder.add_conditional_edges(
        NODE_DOCUMENT_INGEST,
        _route_document,
        {
            NODE_DOCUMENT_INGEST: NODE_DOCUMENT_INGEST,
            NODE_FOLLOWUP: NODE_FOLLOWUP,
            NODE_SAFETY_BEFORE_DOC: NODE_SAFETY_BEFORE_DOC,
            NODE_ESCALATE: NODE_ESCALATE,
            END: END,
        },
    )
    builder.add_conditional_edges(
        NODE_FOLLOWUP,
        _route_followup,
        {
            NODE_FOLLOWUP: NODE_FOLLOWUP,
            NODE_SAFETY_BEFORE_RESPOND: NODE_SAFETY_BEFORE_RESPOND,
            NODE_ESCALATE: NODE_ESCALATE,
            END: END,
        },
    )
    builder.add_conditional_edges(
        NODE_SAFETY_BEFORE_CLARIFY,
        _gate_route(NODE_CLARIFY),
        {NODE_CLARIFY: NODE_CLARIFY, NODE_ESCALATE: NODE_ESCALATE, END: END},
    )
    builder.add_conditional_edges(
        NODE_SAFETY_BEFORE_CONFIRM,
        _gate_route(NODE_WAIT_CONFIRM),
        {NODE_WAIT_CONFIRM: NODE_WAIT_CONFIRM, NODE_ESCALATE: NODE_ESCALATE, END: END},
    )
    builder.add_conditional_edges(
        NODE_SAFETY_BEFORE_DOC,
        _gate_route(NODE_NEEDS_DOCUMENT),
        {NODE_NEEDS_DOCUMENT: NODE_NEEDS_DOCUMENT, NODE_ESCALATE: NODE_ESCALATE, END: END},
    )
    builder.add_conditional_edges(
        NODE_SAFETY_BEFORE_RESPOND,
        _gate_route(NODE_RESPOND),
        {NODE_RESPOND: NODE_RESPOND, NODE_ESCALATE: NODE_ESCALATE, END: END},
    )

    builder.add_edge(NODE_CLARIFY, END)
    builder.add_edge(NODE_WAIT_CONFIRM, END)
    builder.add_edge(NODE_NEEDS_DOCUMENT, END)
    builder.add_edge(NODE_ESCALATE, END)
    builder.add_edge(NODE_RESPOND, END)

    return builder.compile(checkpointer=get_checkpointer())


@lru_cache
def get_graph() -> StateGraph:
    return build_graph()