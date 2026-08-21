"""Tool registry for agent nodes.

Each :class:`ToolSpec` wraps a real Phase 2 tool with a Pydantic args schema.
Arguments emitted by the LLM are validated against the schema before any tool
executes, so malformed input never reaches the database.

Phase 4: tools are partitioned into per-node registries so each specialist
agent only sees the tools for its own responsibility:

* ``SAFETY_TOOLS``      — Safety & Escalation node (escalation + audit).
* ``ROUTING_TOOLS``     — Department Routing node (department lookup only).
* ``APPOINTMENT_TOOLS`` — Appointment node (slots + booking).
* ``DOCUMENT_TOOLS``    — Document node (documents only).
* ``FOLLOWUP_TOOLS``    — Follow-up node (reminders only).

Phase 6: Insurance Eligibility and Billing agents:

* ``INSURANCE_TOOLS``   — Insurance Eligibility node (policy lookup + eligibility check).
* ``BILLING_TOOLS``     — Billing node (fee schedule + billing explanation).

Each node also carries its own completion (decision) tool — the one tool that
signals "my step is done" and routes the graph forward.
"""

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.db.session import Base
from app.tools.appointments import (
    book_appointment,
    cancel_appointment,
    get_appointment,
    reschedule_appointment,
)
from app.tools.audit import log_audit
from app.tools.departments import find_department
from app.tools.documents import (
    attach_document_to_appointment,
    classify_document,
    get_patient_documents,
)
from app.tools.escalations import create_escalation
from app.tools.reminders import create_reminder
from app.tools.slots import list_available_slots
from app.tools.insurance import lookup_insurance, check_eligibility
from app.tools.billing import lookup_fee_items, generate_billing_explanation


def _parse_dt(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"'{value}' is not a valid ISO-8601 datetime (expected e.g. 2026-08-26T09:00:00Z)"
        ) from exc


class FindDepartmentArgs(BaseModel):
    query: str = Field(description="Exact department name or code, case-insensitive.")


class ListAvailableSlotsArgs(BaseModel):
    from_time: str = Field(description="ISO-8601 start of the window, e.g. 2026-08-26T00:00:00Z")
    to_time: str = Field(description="ISO-8601 end of the window (exclusive), e.g. 2026-08-26T23:59:59Z")
    doctor_id: int | None = Field(default=None, description="Optional doctor filter.")
    department_id: int | None = Field(default=None, description="Optional department filter.")


class BookAppointmentArgs(BaseModel):
    patient_id: int
    department_id: int
    doctor_id: int
    slot_id: int
    visit_type: str = Field(default="consultation", description="e.g. consultation, follow_up, procedure")
    reason: str | None = Field(default=None, description="Short reason for the visit.")


class RescheduleAppointmentArgs(BaseModel):
    appointment_id: int
    new_slot_id: int


class CancelAppointmentArgs(BaseModel):
    appointment_id: int
    reason: str | None = None


class GetAppointmentArgs(BaseModel):
    appointment_id: int


class CreateReminderArgs(BaseModel):
    patient_id: int
    reminder_type: str = Field(default="appointment", description="appointment or follow_up")
    scheduled_for: str | None = Field(default=None, description="ISO-8601 datetime for the reminder.")
    appointment_id: int | None = Field(default=None, description="Related appointment, if any.")
    channel: str = Field(default="in_app", description="email, sms or in_app")
    message: str | None = None


class CreateEscalationArgs(BaseModel):
    reason: str = Field(description="Short human-readable reason for the escalation.")
    severity: Literal["low", "medium", "high", "critical"] = Field(
        default="medium",
        description="critical for emergency/safety-of-life, high for potential harm, "
        "medium for sensitive/clinical content, low otherwise.",
    )
    details: str | None = Field(default=None, description="Free-text context for the reviewer.")
    workflow_run_id: int | None = Field(default=None, description="Filled automatically by the system.")
    patient_id: int | None = Field(default=None, description="Filled automatically by the system.")


class LogAuditArgs(BaseModel):
    action: str = Field(description="Audit action name, e.g. 'safety.screen'.")
    entity_type: str = Field(description="Entity type, e.g. 'WorkflowRun'.")
    entity_id: int | None = Field(default=None, description="Related entity id, if any.")
    details: dict | None = Field(default=None, description="Structured details.")


class GetPatientDocumentsArgs(BaseModel):
    patient_id: int


class ClassifyDocumentArgs(BaseModel):
    filename: str = Field(description="Uploaded file name, e.g. 'ecg_report.pdf'.")
    content: str | None = Field(default=None, description="Optional first bytes of text content.")


class AttachDocumentArgs(BaseModel):
    document_id: int
    appointment_id: int


class CompleteSafetyScreenArgs(BaseModel):
    safe: bool = Field(description="true when the content is safe administrative content.")
    reason: str = Field(description="One-line justification for the verdict.")


class CompleteRoutingArgs(BaseModel):
    department_id: int | None = Field(
        default=None,
        description="Id of the single clearly-identified department, or null when clarification is needed.",
    )
    clarify_question: str | None = Field(
        default=None, description="Specific question to the patient when the department is ambiguous."
    )
    needs_booking: bool = Field(default=False, description="true when the request requires booking an appointment.")
    needs_document: bool = Field(default=False, description="true when the request requires patient documents (e.g. ECG).")
    needs_reminder: bool = Field(default=False, description="true when the request asks for a reminder or follow-up.")


class CompleteAppointmentArgs(BaseModel):
    appointment_id: int | None = Field(
        default=None, description="Id of the booked appointment, or null when no booking is possible/needed."
    )
    message: str = Field(description="One-line status of the appointment step.")


class CompleteDocumentCheckArgs(BaseModel):
    document_id: int | None = Field(default=None, description="Id of the verified/attached document, if any.")
    missing_documents: list[str] = Field(default_factory=list, description="Document types still missing, e.g. ['ecg'].")
    message: str = Field(description="One-line status of the document step.")


class CompleteFollowupArgs(BaseModel):
    reminder_id: int | None = Field(default=None, description="Id of the created reminder, if any.")
    message: str = Field(description="One-line status of the follow-up step.")


class LookupInsuranceArgs(BaseModel):
    patient_id: int


class CheckEligibilityArgs(BaseModel):
    appointment_id: int


class CompleteInsuranceCheckArgs(BaseModel):
    insurance_check_id: int | None = Field(
        default=None, description="Id of the eligibility check record, or null if no policy found."
    )
    eligibility_status: str = Field(
        description="covered, needs_preauthorization, not_covered, or no_policy."
    )
    message: str = Field(description="One-line status of the insurance step.")


class LookupFeeItemsArgs(BaseModel):
    department_id: int
    category: str | None = Field(default=None, description="Optional filter: consultation, follow_up, procedure.")


class GenerateBillingExplanationArgs(BaseModel):
    appointment_id: int


class CompleteBillingArgs(BaseModel):
    billing_explanation_id: int | None = Field(
        default=None, description="Id of the billing explanation record."
    )
    estimated_cost: str | None = Field(default=None, description="Estimated total as a decimal string, e.g. '150.00'.")
    message: str = Field(description="One-line status of the billing step.")


def _slots_with_window(
    session: Session,
    from_time: str,
    to_time: str,
    **kwargs: Any,
) -> list:
    """Adapter: the underlying Phase 2 tool wants datetimes, the LLM sends ISO strings."""
    return list_available_slots(
        session,
        _parse_dt(from_time),
        _parse_dt(to_time),
        **kwargs,
    )


def _reminder_with_scheduled_for(
    session: Session,
    scheduled_for: str | None = None,
    **kwargs: Any,
) -> Any:
    """Adapter: the underlying Phase 2 tool wants a datetime, the LLM sends an ISO string."""
    if scheduled_for:
        scheduled_for = _parse_dt(scheduled_for)
    return create_reminder(session, scheduled_for=scheduled_for, **kwargs)


def _classify_document(session: Session, filename: str, content: str | None = None) -> str:
    """Adapter: the classifier is a pure function; the ToolSpec protocol passes a session."""
    return classify_document(filename, content)


def _log_audit_event(
    session: Session,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    details: dict | None = None,
) -> dict:
    """Expose the Phase 2 audit logger to the Safety node for screening evidence."""
    event = log_audit(
        session,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    session.commit()
    return {"audit_event_id": event.id, "action": action, "entity_type": entity_type}


def _serialize(value: Any) -> Any:
    """Convert tool results (ORM objects / primitives) to a JSON-safe structure."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Base):
        return {
            column.key: _serialize(getattr(value, column.key))
            for column in inspect(value).mapper.column_attrs
        }
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return str(value)


@dataclass(frozen=True)
class ToolSpec:
    """A Phase 2 tool exposed to an LLM with a validated Pydantic args schema."""

    name: str
    description: str
    args_schema: type[BaseModel]
    func: Callable[..., Any]
    requires_confirmation: bool = False
    _schema: dict = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_schema",
            {
                "type": "function",
                "function": {
                    "name": self.name,
                    "description": self.description,
                    "parameters": self.args_schema.model_json_schema(),
                },
            },
        )

    @property
    def schema(self) -> dict:
        return self._schema

    def execute(self, session: Session, **validated_args: Any) -> dict:
        result = self.func(session, **validated_args)
        return _serialize(result)


SAFETY_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="create_escalation",
        description="Escalate content that must be reviewed by a human (clinical, prescription, "
        "emergency, or sensitive content). Creates an open Escalation record.",
        args_schema=CreateEscalationArgs,
        func=create_escalation,
    ),
    ToolSpec(
        name="log_audit_event",
        description="Write an audit event as evidence of the screening (e.g. 'safety.screen').",
        args_schema=LogAuditArgs,
        func=_log_audit_event,
    ),
    ToolSpec(
        name="complete_safety_screen",
        description="Call ONLY when the screening is finished: reports whether the content "
        "passed as safe administrative content.",
        args_schema=CompleteSafetyScreenArgs,
        func=lambda session, **kwargs: {"safe": kwargs.get("safe"), "reason": kwargs.get("reason")},
    ),
]

ROUTING_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="find_department",
        description="Find a department by exact name or code (case-insensitive), e.g. 'Cardiology'.",
        args_schema=FindDepartmentArgs,
        func=find_department,
    ),
    ToolSpec(
        name="complete_routing",
        description="Call ONLY when routing is decided: report the single identified department "
        "(or ask for clarification) plus which downstream steps the request needs.",
        args_schema=CompleteRoutingArgs,
        func=lambda session, **kwargs: {"routed": True},
    ),
]

APPOINTMENT_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="list_available_slots",
        description="List unbooked appointment slots in a time window, optionally filtered by doctor or department.",
        args_schema=ListAvailableSlotsArgs,
        func=_slots_with_window,
    ),
    ToolSpec(
        name="book_appointment",
        description="Book an appointment for a patient in a department with a doctor on a specific free slot.",
        args_schema=BookAppointmentArgs,
        func=book_appointment,
        requires_confirmation=True,
    ),
    ToolSpec(
        name="reschedule_appointment",
        description="Move an existing appointment to a new free slot.",
        args_schema=RescheduleAppointmentArgs,
        func=reschedule_appointment,
        requires_confirmation=True,
    ),
    ToolSpec(
        name="cancel_appointment",
        description="Cancel an existing appointment and free its slot.",
        args_schema=CancelAppointmentArgs,
        func=cancel_appointment,
        requires_confirmation=True,
    ),
    ToolSpec(
        name="get_appointment",
        description="Look up an appointment by id.",
        args_schema=GetAppointmentArgs,
        func=get_appointment,
    ),
    ToolSpec(
        name="complete_appointment",
        description="Call ONLY when the appointment step is finished: report the booked "
        "appointment id, or null when no booking is possible or needed.",
        args_schema=CompleteAppointmentArgs,
        func=lambda session, **kwargs: {"completed": True},
    ),
]

DOCUMENT_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_patient_documents",
        description="List documents already uploaded for a patient.",
        args_schema=GetPatientDocumentsArgs,
        func=get_patient_documents,
    ),
    ToolSpec(
        name="classify_document",
        description="Classify a document by filename/content into ecg, lab_report, prescription, "
        "referral, id_proof, imaging or other.",
        args_schema=ClassifyDocumentArgs,
        func=_classify_document,
    ),
    ToolSpec(
        name="attach_document_to_appointment",
        description="Attach a verified patient document to the booked appointment.",
        args_schema=AttachDocumentArgs,
        func=attach_document_to_appointment,
    ),
    ToolSpec(
        name="complete_document_check",
        description="Call ONLY when the document step is finished: report the attached document id, "
        "or list which document types are still missing.",
        args_schema=CompleteDocumentCheckArgs,
        func=lambda session, **kwargs: {"checked": True},
    ),
]

FOLLOWUP_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="create_reminder",
        description="Create a reminder (appointment or follow-up) for a patient.",
        args_schema=CreateReminderArgs,
        func=_reminder_with_scheduled_for,
    ),
    ToolSpec(
        name="complete_followup",
        description="Call ONLY when the follow-up step is finished: report the created reminder id, "
        "or confirm no reminder is needed.",
        args_schema=CompleteFollowupArgs,
        func=lambda session, **kwargs: {"completed": True},
    ),
]

INSURANCE_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="lookup_insurance",
        description="Look up a patient's insurance policy status (active, expired, inactive, or missing).",
        args_schema=LookupInsuranceArgs,
        func=lookup_insurance,
    ),
    ToolSpec(
        name="check_eligibility",
        description="Run an eligibility pre-check for a booked appointment against the patient's policy. "
        "Returns a result grounded in the patient's real policy data.",
        args_schema=CheckEligibilityArgs,
        func=check_eligibility,
    ),
    ToolSpec(
        name="complete_insurance_check",
        description="Call ONLY when the insurance eligibility step is done: report the eligibility status "
        "and the check record id.",
        args_schema=CompleteInsuranceCheckArgs,
        func=lambda session, **kwargs: {"completed": True},
    ),
]

BILLING_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="lookup_fee_items",
        description="Look up fee schedule items for a department, optionally filtered by category.",
        args_schema=LookupFeeItemsArgs,
        func=lookup_fee_items,
    ),
    ToolSpec(
        name="generate_billing_explanation",
        description="Generate a billing explanation with line items from the fee schedule for a booked appointment.",
        args_schema=GenerateBillingExplanationArgs,
        func=generate_billing_explanation,
    ),
    ToolSpec(
        name="complete_billing",
        description="Call ONLY when the billing step is done: report the explanation id and estimated cost.",
        args_schema=CompleteBillingArgs,
        func=lambda session, **kwargs: {"completed": True},
    ),
]


def tool_schema_dicts(tools: list[ToolSpec]) -> list[dict]:
    return [tool.schema for tool in tools]


def find_tool(tools: list[ToolSpec], name: str) -> ToolSpec | None:
    return next((tool for tool in tools if tool.name == name), None)


def dump_json(value: Any) -> str:
    return json.dumps(value, default=str)