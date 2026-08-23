"""Agent nodes.

Phase 4: the graph is split into specialist agents, each with its own system
prompt and a scoped tool set:

* :class:`SafetyAgentNode`   — Safety & Escalation: screens every incoming
  request (entry) and every draft output of the other agents (gates) with the
  escalation + audit tools.  Anything unsafe routes to the ``escalate`` terminal
  instead of reaching the patient.
* :class:`RoutingAgentNode`  — Department Routing: only the department lookup
  tool; decides the single department or asks the patient to clarify.
* :class:`AppointmentAgentNode` — Appointment: only slot/booking tools; books
  and pauses for patient confirmation.
* :class:`DocumentAgentNode` — Document: only document tools; verifies/attaches
  required documents or reports what is missing.
* :class:`FollowupAgentNode` — Follow-up: only the reminder tool.

Each agent runs one LLM turn per graph step and carries its own completion
(decision) tool — the only way a step is marked done.  The graph drives the
loop with conditional self-edges so the Postgres checkpointer persists the
accumulated state after every single step (what makes restart-and-resume work).
"""

import json
from datetime import datetime

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.core import tools as tool_mod
from app.core.llm import groq_client
from app.core.persistence import now_iso, update_workflow_run
from app.core.state import (
    RUN_STATUS_AWAITING_CLARIFICATION,
    RUN_STATUS_AWAITING_CONFIRMATION,
    RUN_STATUS_AWAITING_DOCUMENT,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_ESCALATED,
    RUN_STATUS_FAILED,
    RUN_STATUS_IN_PROGRESS,
    WorkflowState,
)
from app.db.session import SessionLocal

MAX_FAILED_ATTEMPTS = 3
MAX_TURNS = 12

NODE_SAFETY_SCREEN = "safety_screen"
NODE_ROUTE_DEPARTMENT = "route_department"
NODE_BOOK_APPOINTMENT = "book_appointment"
NODE_INSURANCE_CHECK = "insurance_check"
NODE_BILLING_GENERATE = "billing_generate"
NODE_DOCUMENT_INGEST = "document_ingest"
NODE_FOLLOWUP = "followup"
NODE_SAFETY_BEFORE_CLARIFY = "safety_before_clarify"
NODE_SAFETY_BEFORE_CONFIRM = "safety_before_confirm"
NODE_SAFETY_BEFORE_DOC = "safety_before_doc"
NODE_SAFETY_BEFORE_RESPOND = "safety_before_respond"
NODE_CLARIFY = "clarify"
NODE_WAIT_CONFIRM = "wait_confirm"
NODE_NEEDS_DOCUMENT = "needs_document"
NODE_ESCALATE = "escalate"
NODE_RESPOND = "respond"

SAFETY_SCREEN_TOOL = "complete_safety_screen"
ROUTING_TOOL = "complete_routing"
APPOINTMENT_TOOL = "complete_appointment"
INSURANCE_CHECK_TOOL = "complete_insurance_check"
BILLING_TOOL = "complete_billing"
DOCUMENT_CHECK_TOOL = "complete_document_check"
FOLLOWUP_TOOL = "complete_followup"

CONTINUE_HINT = (
    "Your step is not complete yet. Use your available tools to make progress, "
    "then call your completion tool when the step is done."
)


def _today() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d")


SAFETY_ENTRY_PROMPT = """You are the Safety & Escalation agent of AgentCare, an AI system for \
patient administration and care coordination. Today's date is {today}.

Your job is to screen the patient's request BEFORE any other agent acts on it. You must distinguish \
between genuine emergencies and routine administrative requests that mention symptoms.

ESCALATE (call create_escalation) if the request contains:
- Requests for medical diagnosis, treatment advice, prescriptions, dosages, or medication instructions,
- Genuine emergency or life-threatening symptoms: chest pain, difficulty breathing, severe bleeding, \
fainting, stroke symptoms (sudden weakness, slurred speech), severe allergic reactions, loss of \
consciousness, severe abdominal pain, high fever with confusion,
- Self-harm or harm to others,
- Explicit requests for the system to diagnose, treat, or prescribe (e.g. "what is wrong with me", \
"what medicine should I take").

DO NOT ESCALATE — route normally to Department Routing if:
- The patient mentions a mild or routine symptom (headache, skin rash, mild cough, back pain, \
earache, mild fever, etc.) purely as the reason for wanting an appointment or booking. This is \
administrative routing information, not a diagnosis request.
- The patient is asking to see a doctor, book an appointment, or get routed to a department, \
and mentions a symptom only to explain what the visit is about.

Rules:
1. If the request is safe, routine administrative content, call complete_safety_screen(safe=true, \
reason="...").
2. If it must be escalated, call create_escalation with an appropriate severity (critical for \
emergency or safety-of-life, high for potential harm, medium for clinical or sensitive content) \
and a clear reason, then call complete_safety_screen(safe=false, reason="...").
3. Never answer the request yourself and never give clinical advice.
4. When in doubt about severity, escalate — patient safety comes first."""

SAFETY_GATE_PROMPT = """You are the Safety & Escalation gate of AgentCare. Today's date is {today}.

You run immediately AFTER another agent produced output and BEFORE anything is shown to the \
patient. Review the most recent agent output in the conversation for clinical advice, diagnoses, \
prescriptions, emergency language, or anything that must be reviewed by a human.

Rules:
1. If the output is safe administrative content, call complete_safety_screen(safe=true, reason="...").
2. If it must be escalated, call create_escalation with an appropriate severity and a clear reason, \
then call complete_safety_screen(safe=false, reason="...").
3. Never alter the output; only screen it."""

ROUTING_PROMPT = """You are the Department Routing agent of AgentCare. Today's date is {today}.

Map the patient's request to exactly ONE real department. Rules:
1. Use find_department to look up the department (e.g. 'Cardiology') and use the id from its \
result. Never invent department ids.
2. If the request identifies a single clear department, call complete_routing(department_id=<id>, \
needs_booking=<bool>, needs_document=<bool>, needs_reminder=<bool>).
3. If the request does not clearly map to one department (ambiguous, contradictory, or no match), \
do NOT guess: call complete_routing(department_id=null, \
clarify_question="<one specific question to the patient>", ...).
4. needs_booking=true when an appointment must be booked. needs_document=true when the request \
mentions patient documents such as an ECG. needs_reminder=true when a reminder or follow-up is \
requested."""

APPOINTMENT_PROMPT = """You are the Appointment agent of AgentCare. Today's date is {today}. The \
request was routed to department {department_name} (id {department_id}) for patient {patient_id}.

Rules:
1. Call list_available_slots for a sensible window (slots exist on weekdays) with the \
department_id filter and prefer the earliest sensible slot.
2. Call book_appointment with the patient id {patient_id}, the routed department id, the real \
doctor and slot ids from the listing, and the visit type. The booking pauses for patient \
confirmation, so never book twice.
3. If no slot is available or the booking is impossible, call \
complete_appointment(appointment_id=null, message="...") to move on.
4. A successful book_appointment completes this step itself; do not call complete_appointment \
after booking."""

DOCUMENT_PROMPT = """You are the Medical Document Coordination agent of AgentCare. Today's date \
is {today}. Patient {patient_id}{appointment_clause}.

Rules:
1. If the routing decision requires documents: call get_patient_documents(patient_id) to see what \
is on file, classify_document(filename, content) to verify the type of the relevant document, and \
attach_document_to_appointment(document_id, appointment_id) to link the verified document to the \
appointment when one exists.
2. If a required document type is missing, call complete_document_check(missing_documents=["ecg"], \
message="...").
3. If everything required is present and attached, call \
complete_document_check(document_id=<id>, message="...").
4. If no documents are required for this request, call \
complete_document_check(message="No documents required")."""

FOLLOWUP_PROMPT = """You are the Follow-up agent of AgentCare. Today's date is {today}. \
Patient {patient_id}{appointment_clause}.

Rules:
1. Call create_reminder for the patient, linked to the appointment. The tool will \
auto-generate the correct message from real appointment data — do NOT pass a message \
parameter. The reminder must be scheduled ONE DAY BEFORE the appointment \
(the appointment is at {appointment_at}). Then call \
complete_followup(reminder_id=<id>, message="Reminder created.").
2. If the appointment is already in the past or no valid date is provided, call \
complete_followup(message="Reminder could not be created — invalid date")."""

INSURANCE_PROMPT = """You are the Insurance Eligibility agent of AgentCare. Today's date is {today}. \
Patient {patient_id} has a booked appointment #{appointment_id} in {department_name}.

Rules:
1. Call lookup_insurance(patient_id={patient_id}) to see the patient's insurance status.
2. If a policy exists, call check_eligibility(appointment_id={appointment_id}) to run the \
eligibility pre-check against the real policy and visit type.
3. Call complete_insurance_check with the eligibility_status (covered, needs_preauthorization, \
not_covered, or no_policy), the insurance_check_id if a check was created, and a one-line message.
4. Never guarantee payment or coverage. The result is an estimate only."""

BILLING_PROMPT = """You are the Billing agent of AgentCare. Today's date is {today}. \
Patient {patient_id} has a booked appointment #{appointment_id} in {department_name}.

Rules:
1. Call generate_billing_explanation(appointment_id={appointment_id}) to assemble real line items \
from the fee schedule for this department and visit type.
2. Call complete_billing with the billing_explanation_id, the estimated total cost as a string, \
and a one-line message.
3. Never issue a legally binding invoice. The result is an explanation of expected costs only."""


class BaseAgentNode:
    """One LLM turn per invocation; the graph drives the loop via self-edges."""

    node_name: str
    completion_tool: str | None

    def __init__(self, tool_specs: list[tool_mod.ToolSpec], llm_factory=None):
        self.tool_specs = tool_specs
        self.llm_factory = llm_factory or (lambda: groq_client.get_llm())

    def _system_prompt(self, state: WorkflowState) -> str:
        raise NotImplementedError

    def _persist_step(
        self, state: WorkflowState, *, status: str, current_step: str, summary: str
    ) -> None:
        run_id = state.get("workflow_run_id")
        thread_id = state.get("thread_id")
        if run_id is None:
            return
        update_workflow_run(
            run_id,
            thread_id=thread_id,
            status=status,
            current_step=current_step,
            summary=summary,
            state_payload={
                "status_message": summary,
                "thread_id": thread_id,
                "updated_at": now_iso(),
            },
        )

    def _execute_tool_call(
        self, session: Session, state: WorkflowState, call: dict
    ) -> tuple[ToolMessage, dict | None]:
        """Validate args with Pydantic, execute the real tool, return message + result.

        Returns (tool_message, executed_result) where executed_result is None when
        validation failed or the tool raised.
        """
        spec = tool_mod.find_tool(self.tool_specs, call["name"])
        if spec is None:
            available = ", ".join(t.name for t in self.tool_specs)
            return (
                ToolMessage(
                    content=f"Unknown tool '{call['name']}'. Available tools: {available}.",
                    tool_call_id=call["id"],
                ),
                None,
            )
        try:
            args = spec.args_schema.model_validate(call["args"])
        except ValidationError as exc:
            details = [
                {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]}
                for err in exc.errors()
            ]
            message = (
                f"Invalid arguments for '{call['name']}': {json.dumps(details)}. "
                "Fix the arguments and call the tool again with correct types and "
                "ISO-8601 datetimes."
            )
            return ToolMessage(content=message, tool_call_id=call["id"]), None

        args_json = args.model_dump(mode="json")
        if call["name"] == "create_escalation":
            if args_json.get("workflow_run_id") is None:
                args_json["workflow_run_id"] = state.get("workflow_run_id")
            if args_json.get("patient_id") is None:
                args_json["patient_id"] = state.get("patient_id")
        try:
            result = spec.execute(session, **args_json)
        except Exception as exc:  # noqa: BLE001 - tool errors are fed back to the LLM
            session.rollback()
            return (
                ToolMessage(
                    content=f"Tool '{call['name']}' failed: {exc}",
                    tool_call_id=call["id"],
                ),
                {"name": call["name"], "args": args_json, "ok": False, "error": str(exc)},
            )

        return (
            ToolMessage(
                content=tool_mod.dump_json({"ok": True, "result": result}),
                tool_call_id=call["id"],
            ),
            {"name": call["name"], "args": args_json, "ok": True, "result": result},
        )

    def _on_tool_result(self, result: dict) -> dict:
        """Extra state deltas captured from a successful tool result (per-node)."""
        return {}

    def _apply_completion(self, args: BaseModel) -> dict:
        """State deltas applied when the node's completion tool is called."""
        return {}

    def _filter_messages(self, messages: list[BaseMessage]) -> list[BaseMessage]:
        """Strip AIMessages whose tool_calls reference tools outside this node's set.

        Groq validates that every tool_call in the conversation history belongs to
        the current request's tools list.  When the graph resumes after a checkpoint,
        the history may contain tool_calls from earlier nodes (safety, routing, etc.)
        whose tools are not bound on this node, causing a 400 error.
        """
        allowed = {t.name for t in self.tool_specs}
        filtered: list[BaseMessage] = []
        skip_tool_call_ids: set[str] = set()

        for msg in messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                bad_calls = [tc for tc in msg.tool_calls if tc["name"] not in allowed]
                if bad_calls:
                    skip_tool_call_ids.update(tc["id"] for tc in bad_calls)
                    good_calls = [tc for tc in msg.tool_calls if tc["name"] in allowed]
                    if good_calls:
                        filtered.append(AIMessage(
                            content=msg.content,
                            tool_calls=good_calls,
                            id=msg.id,
                        ))
                    continue
            if isinstance(msg, ToolMessage) and msg.tool_call_id in skip_tool_call_ids:
                continue
            filtered.append(msg)
        return filtered

    def __call__(self, state: WorkflowState) -> dict:
        llm = self.llm_factory().bind_tools(tool_mod.tool_schema_dicts(self.tool_specs))
        messages: list[BaseMessage] = [SystemMessage(content=self._system_prompt(state))]
        messages.extend(self._filter_messages(state.get("messages", [])))

        response = llm.invoke(messages)
        new_messages: list[BaseMessage] = [response]
        executed: list[dict] = []
        ran_side_effect = False
        failed_this_turn = 0
        completion_deltas: dict = {}

        calls = getattr(response, "tool_calls", None) or []
        work_calls = [call for call in calls if call["name"] != self.completion_tool]
        completion_calls = [call for call in calls if call["name"] == self.completion_tool]

        session = SessionLocal()
        try:
            for call in work_calls:
                tool_message, result = self._execute_tool_call(session, state, call)
                new_messages.append(tool_message)
                if result is None:
                    failed_this_turn += 1
                    continue
                executed.append(result)
                if result["ok"]:
                    spec = tool_mod.find_tool(self.tool_specs, call["name"])
                    if spec is not None and spec.requires_confirmation:
                        ran_side_effect = True
                    completion_deltas.update(self._on_tool_result(result))
                    self._persist_step(
                        state,
                        status=RUN_STATUS_IN_PROGRESS,
                        current_step=call["name"],
                        summary=self._summarize_tool(result),
                    )
                else:
                    failed_this_turn += 1

            for call in completion_calls:
                spec = tool_mod.find_tool(self.tool_specs, self.completion_tool)
                if spec is None:
                    continue
                try:
                    args = spec.args_schema.model_validate(call["args"])
                except ValidationError as exc:
                    details = [
                        {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]}
                        for err in exc.errors()
                    ]
                    new_messages.append(
                        ToolMessage(
                            content=(
                                f"Invalid arguments for '{self.completion_tool}': "
                                f"{json.dumps(details)}."
                            ),
                            tool_call_id=call["id"],
                        )
                    )
                    failed_this_turn += 1
                    continue
                completion_deltas.update(self._apply_completion(args))
                new_messages.append(
                    ToolMessage(
                        content=f"Step recorded: {args.model_dump(mode='json')}",
                        tool_call_id=call["id"],
                    )
                )
                executed.append(
                    {
                        "name": self.completion_tool,
                        "args": args.model_dump(mode="json"),
                        "ok": True,
                        "result": args.model_dump(mode="json"),
                    }
                )
                self._persist_step(
                    state,
                    status=RUN_STATUS_IN_PROGRESS,
                    current_step=self.completion_tool,
                    summary=completion_deltas.get(
                        "status_message", f"{self.node_name} step done."
                    ),
                )
        finally:
            session.close()

        turns = state.get("turns", 0) + 1
        previous_failures = state.get("failed_attempts", 0)
        step_done = bool(completion_deltas) or ran_side_effect
        if ran_side_effect:
            failed_attempts = 0
            status = RUN_STATUS_AWAITING_CONFIRMATION
            summary = f"{self._summarize_tool(executed[-1])} Awaiting patient confirmation."
        elif step_done:
            failed_attempts = 0
            status = RUN_STATUS_IN_PROGRESS
            summary = completion_deltas.get(
                "status_message", self._summarize_tool(executed[-1]) or "Step done."
            )
        elif executed and any(item["ok"] for item in executed):
            failed_attempts = 0
            status = RUN_STATUS_IN_PROGRESS
            summary = self._summarize_tool(executed[-1]) or "Continuing the request."
        elif failed_this_turn:
            failed_attempts = previous_failures + failed_this_turn
            if failed_attempts >= MAX_FAILED_ATTEMPTS:
                status = RUN_STATUS_FAILED
                summary = (
                    f"Failed: {failed_attempts} consecutive invalid tool calls were not "
                    "recoverable. This request needs human review."
                )
            else:
                status = RUN_STATUS_IN_PROGRESS
                summary = "Retrying after an invalid tool call."
        else:
            failed_attempts = 0
            status = RUN_STATUS_IN_PROGRESS
            summary = "Continuing the request."
            new_messages.append(HumanMessage(content=CONTINUE_HINT))

        if status != RUN_STATUS_COMPLETED and turns > MAX_TURNS:
            status = RUN_STATUS_FAILED
            summary = (
                f"Failed: the run exceeded {MAX_TURNS} turns without completing. "
                "This request needs human review."
            )

        self._persist_step(
            state,
            status=status,
            current_step=executed[-1]["name"] if executed else self.node_name,
            summary=summary,
        )

        deltas: dict = {
            "messages": new_messages,
            "tool_results": executed,
            "failed_attempts": failed_attempts,
            "turns": turns,
            "status": status,
            "status_message": summary,
        }
        if executed:
            deltas["current_step"] = executed[-1]["name"]
        deltas.update(completion_deltas)
        return deltas

    @staticmethod
    def _summarize_tool(result: dict) -> str:
        name = result.get("name")
        payload = result.get("result") or {}
        if name == "book_appointment" and isinstance(payload, dict):
            return (
                f"Booked appointment #{payload.get('id')} for "
                f"{payload.get('scheduled_for')} (status {payload.get('status')})."
            )
        if name == "cancel_appointment" and isinstance(payload, dict):
            return f"Cancelled appointment #{payload.get('id')}."
        if name == "reschedule_appointment" and isinstance(payload, dict):
            return f"Rescheduled appointment #{payload.get('id')}."
        if name == "create_reminder" and isinstance(payload, dict):
            return f"Created reminder #{payload.get('id')} ({payload.get('reminder_type')})."
        if name == "find_department" and isinstance(payload, dict):
            return f"Found department #{payload.get('id')} ({payload.get('name')})."
        if name == "list_available_slots" and isinstance(payload, list):
            return f"Found {len(payload)} available slot(s)."
        if name == "get_appointment" and isinstance(payload, dict):
            return f"Found appointment #{payload.get('id')}."
        if name == "create_escalation" and isinstance(payload, dict):
            return (
                f"Escalated (severity {payload.get('severity')}) for human review "
                f"as escalation #{payload.get('id')}."
            )
        if name == "attach_document_to_appointment" and isinstance(payload, dict):
            return f"Attached document #{payload.get('id')} to appointment #{payload.get('appointment_id')}."
        if name == "classify_document":
            return f"Document classified as {payload}."
        if name == "get_patient_documents" and isinstance(payload, list):
            return f"Found {len(payload)} document(s) on file."
        if name == "log_audit_event" and isinstance(payload, dict):
            return f"Audit event {payload.get('action')} recorded."
        if not result.get("ok"):
            return f"Tool '{name}' failed: {result.get('error')}"
        return f"Executed {name}."


class SafetyAgentNode(BaseAgentNode):
    """Screens content with the escalation + audit tools. Entry node and pre-output gates."""

    completion_tool = SAFETY_SCREEN_TOOL

    def __init__(
        self,
        tool_specs: list[tool_mod.ToolSpec],
        *,
        gate: bool = False,
        llm_factory=None,
    ):
        super().__init__(tool_specs, llm_factory=llm_factory)
        self.gate = gate
        self.node_name = NODE_SAFETY_SCREEN if not gate else "safety_gate"

    def _system_prompt(self, state: WorkflowState) -> str:
        template = SAFETY_GATE_PROMPT if self.gate else SAFETY_ENTRY_PROMPT
        return template.format(today=_today())

    def _on_tool_result(self, result: dict) -> dict:
        if result["name"] == "create_escalation" and result.get("ok"):
            payload = result.get("result") or {}
            return {
                "escalation_id": payload.get("id"),
                "escalation_reason": payload.get("reason")
                or result.get("args", {}).get("reason"),
            }
        return {}

    def _apply_completion(self, args: BaseModel) -> dict:
        data = args.model_dump(mode="json")
        safe = bool(data.get("safe"))
        return {
            "node_done": self.node_name,
            "safety_verdict": "safe" if safe else "escalate",
            "safety_reason": data.get("reason"),
            "status_message": (
                "Safety screening passed: content is safe administrative material."
                if safe
                else "Safety screening flagged the content for human review."
            ),
        }


class RoutingAgentNode(BaseAgentNode):
    """Department Routing: only the department lookup tool + its completion tool."""

    node_name = NODE_ROUTE_DEPARTMENT
    completion_tool = ROUTING_TOOL

    def _system_prompt(self, state: WorkflowState) -> str:
        return ROUTING_PROMPT.format(today=_today())

    def _on_tool_result(self, result: dict) -> dict:
        payload = result.get("result") or {}
        if result.get("name") == "find_department" and isinstance(payload, dict):
            return {"department_name": payload.get("name")}
        return {}

    def _apply_completion(self, args: BaseModel) -> dict:
        data = args.model_dump(mode="json")
        if data.get("clarify_question"):
            return {
                "node_done": self.node_name,
                "clarify_question": data["clarify_question"],
                "department_id": None,
                "needs_booking": bool(data.get("needs_booking", False)),
                "needs_document": bool(data.get("needs_document", False)),
                "needs_reminder": bool(data.get("needs_reminder", False)),
                "status_message": "Department unclear; asked the patient to clarify.",
            }
        return {
            "node_done": self.node_name,
            "department_id": data.get("department_id"),
            "clarify_question": None,
            "needs_booking": bool(data.get("needs_booking", False)),
            "needs_document": bool(data.get("needs_document", False)),
            "needs_reminder": bool(data.get("needs_reminder", False)),
            "status_message": f"Routed to department #{data.get('department_id')}.",
        }


class AppointmentAgentNode(BaseAgentNode):
    """Appointment: only slot/booking tools; pauses for patient confirmation."""

    node_name = NODE_BOOK_APPOINTMENT
    completion_tool = APPOINTMENT_TOOL

    def _system_prompt(self, state: WorkflowState) -> str:
        return APPOINTMENT_PROMPT.format(
            today=_today(),
            department_name=state.get("department_name", "the routed department"),
            department_id=state.get("department_id", "?"),
            patient_id=state.get("patient_id", "?"),
        )

    def _on_tool_result(self, result: dict) -> dict:
        if not result.get("ok"):
            return {}
        name = result["name"]
        payload = result.get("result") or {}
        if name in ("book_appointment", "reschedule_appointment"):
            return {
                "appointment_id": payload.get("id"),
                "appointment_at": payload.get("scheduled_for"),
                "status_message": self._summarize_tool(result),
            }
        return {}

    def _apply_completion(self, args: BaseModel) -> dict:
        data = args.model_dump(mode="json")
        return {
            "node_done": self.node_name,
            "status_message": data.get("message") or "Appointment step done without booking.",
        }


class DocumentAgentNode(BaseAgentNode):
    """Document: only document tools; verifies/attaches required documents."""

    node_name = NODE_DOCUMENT_INGEST
    completion_tool = DOCUMENT_CHECK_TOOL

    def _system_prompt(self, state: WorkflowState) -> str:
        appointment = state.get("appointment_id")
        clause = (
            f". The appointment is #{appointment}"
            if appointment
            else ". No appointment exists yet; verify documents on file only"
        )
        return DOCUMENT_PROMPT.format(
            today=_today(), patient_id=state.get("patient_id", "?"), appointment_clause=clause
        )

    def _on_tool_result(self, result: dict) -> dict:
        if not result.get("ok"):
            return {}
        name = result["name"]
        payload = result.get("result") or {}
        if name == "attach_document_to_appointment":
            return {
                "document_id": payload.get("id"),
                "document_type": payload.get("document_type"),
                "status_message": self._summarize_tool(result),
            }
        if name == "classify_document":
            return {"document_type": payload if isinstance(payload, str) else "other"}
        return {}

    def _apply_completion(self, args: BaseModel) -> dict:
        data = args.model_dump(mode="json")
        missing = data.get("missing_documents") or []
        if missing:
            return {
                "node_done": self.node_name,
                "missing_documents": missing,
                "document_id": None,
                "status_message": f"Waiting for document(s): {', '.join(missing)}.",
            }
        deltas: dict = {
            "node_done": self.node_name,
            "missing_documents": [],
            "status_message": data.get("message") or "Document check done.",
        }
        if data.get("document_id") is not None:
            deltas["document_id"] = data["document_id"]
        return deltas


class FollowupAgentNode(BaseAgentNode):
    """Follow-up: only the reminder tool."""

    node_name = NODE_FOLLOWUP
    completion_tool = FOLLOWUP_TOOL

    def _system_prompt(self, state: WorkflowState) -> str:
        appointment = state.get("appointment_id")
        clause = (
            f". The appointment is #{appointment}"
            if appointment
            else ". No appointment exists"
        )
        at = state.get("appointment_at") or "an unknown time"
        return FOLLOWUP_PROMPT.format(
            today=_today(),
            patient_id=state.get("patient_id", "?"),
            appointment_clause=clause,
            appointment_at=at,
        )

    def _on_tool_result(self, result: dict) -> dict:
        if not result.get("ok"):
            return {}
        payload = result.get("result") or {}
        if result["name"] == "create_reminder":
            return {"reminder_id": payload.get("id")}
        return {}

    def _apply_completion(self, args: BaseModel) -> dict:
        data = args.model_dump(mode="json")
        deltas: dict = {
            "node_done": self.node_name,
            "status_message": data.get("message") or "Follow-up step done.",
        }
        if data.get("reminder_id") is not None:
            deltas["reminder_id"] = data["reminder_id"]
        return deltas


class InsuranceAgentNode(BaseAgentNode):
    """Insurance Eligibility: policy lookup + eligibility check for the booked appointment."""

    node_name = NODE_INSURANCE_CHECK
    completion_tool = INSURANCE_CHECK_TOOL

    def _system_prompt(self, state: WorkflowState) -> str:
        return INSURANCE_PROMPT.format(
            today=_today(),
            patient_id=state.get("patient_id", "?"),
            appointment_id=state.get("appointment_id", "?"),
            department_name=state.get("department_name", "the routed department"),
        )

    def _on_tool_result(self, result: dict) -> dict:
        if not result.get("ok"):
            return {}
        name = result["name"]
        payload = result.get("result") or {}
        if name == "check_eligibility" and isinstance(payload, dict):
            return {
                "insurance_check_id": payload.get("id"),
                "eligibility_status": payload.get("status"),
            }
        return {}

    def _apply_completion(self, args: BaseModel) -> dict:
        data = args.model_dump(mode="json")
        deltas: dict = {
            "node_done": self.node_name,
            "eligibility_status": data.get("eligibility_status"),
            "status_message": data.get("message") or "Insurance check done.",
        }
        if data.get("insurance_check_id") is not None:
            deltas["insurance_check_id"] = data["insurance_check_id"]
        return deltas


class BillingAgentNode(BaseAgentNode):
    """Billing: fee-schedule line items and plain-language billing explanation."""

    node_name = NODE_BILLING_GENERATE
    completion_tool = BILLING_TOOL

    def _system_prompt(self, state: WorkflowState) -> str:
        return BILLING_PROMPT.format(
            today=_today(),
            patient_id=state.get("patient_id", "?"),
            appointment_id=state.get("appointment_id", "?"),
            department_name=state.get("department_name", "the routed department"),
        )

    def _on_tool_result(self, result: dict) -> dict:
        if not result.get("ok"):
            return {}
        name = result["name"]
        payload = result.get("result") or {}
        if name == "generate_billing_explanation" and isinstance(payload, dict):
            total = None
            if payload.get("summary_text"):
                import re

                match = re.search(r"\$([0-9,]+\.\d{2})", payload["summary_text"])
                if match:
                    total = match.group(1).replace(",", "")
            return {
                "billing_explanation_id": payload.get("id"),
                "estimated_cost": total,
            }
        return {}

    def _apply_completion(self, args: BaseModel) -> dict:
        data = args.model_dump(mode="json")
        deltas: dict = {
            "node_done": self.node_name,
            "estimated_cost": data.get("estimated_cost"),
            "status_message": data.get("message") or "Billing step done.",
        }
        if data.get("billing_explanation_id") is not None:
            deltas["billing_explanation_id"] = data["billing_explanation_id"]
        return deltas


class TerminalNode:
    """A plain (no-LLM) terminal that writes the final run status and message."""

    def __init__(
        self,
        node_name: str,
        status: str,
        summary_fn,
        response_fn=None,
    ):
        self.node_name = node_name
        self.status = status
        self.summary_fn = summary_fn
        self.response_fn = response_fn

    def __call__(self, state: WorkflowState) -> dict:
        summary = self.summary_fn(state)
        deltas: dict = {
            "status": self.status,
            "status_message": summary,
            "current_step": self.node_name,
        }
        if self.response_fn is not None:
            deltas["final_response"] = self.response_fn(state)
        run_id = state.get("workflow_run_id")
        if run_id is not None:
            update_workflow_run(
                run_id,
                thread_id=state.get("thread_id"),
                status=self.status,
                current_step=self.node_name,
                summary=summary,
                state_payload={
                    "status_message": summary,
                    "final_response": deltas.get("final_response"),
                    "thread_id": state.get("thread_id"),
                    "updated_at": now_iso(),
                },
            )
        return deltas


def build_terminals() -> dict[str, TerminalNode]:
    def _escalation_summary(state: WorkflowState) -> str:
        return state.get("escalation_reason") or state.get("safety_reason") or "Escalated."

    return {
        NODE_ESCALATE: TerminalNode(
            NODE_ESCALATE,
            RUN_STATUS_ESCALATED,
            _escalation_summary,
            response_fn=lambda state: (
                "This request has been escalated to a human reviewer. "
                "AgentCare will not act on it."
            ),
        ),
        NODE_CLARIFY: TerminalNode(
            NODE_CLARIFY,
            RUN_STATUS_AWAITING_CLARIFICATION,
            lambda state: state.get("clarify_question") or "Which department do you need?",
            response_fn=lambda state: state.get("clarify_question") or "Which department?",
        ),
        NODE_WAIT_CONFIRM: TerminalNode(
            NODE_WAIT_CONFIRM,
            RUN_STATUS_AWAITING_CONFIRMATION,
            lambda state: (
                f"Appointment #{state.get('appointment_id')} booked for "
                f"{state.get('appointment_at')}. Awaiting patient confirmation."
            ),
            response_fn=lambda state: (
                f"Appointment #{state.get('appointment_id')} is booked for "
                f"{state.get('appointment_at')}. Please confirm to continue."
            ),
        ),
        NODE_NEEDS_DOCUMENT: TerminalNode(
            NODE_NEEDS_DOCUMENT,
            RUN_STATUS_AWAITING_DOCUMENT,
            lambda state: (
                "Waiting for document(s): "
                f"{', '.join(state.get('missing_documents') or [])}."
            ),
            response_fn=lambda state: (
                f"Please provide: {', '.join(state.get('missing_documents') or [])}."
            ),
        ),
        NODE_RESPOND: TerminalNode(
            NODE_RESPOND,
            RUN_STATUS_COMPLETED,
            lambda state: "Request fully handled.",
            response_fn=_build_final_response,
        ),
    }


def _build_final_response(state: WorkflowState) -> str:
    parts: list[str] = []
    appointment_id = state.get("appointment_id")
    appointment_at = state.get("appointment_at")
    if appointment_id:
        when = f" for {appointment_at}" if appointment_at else ""
        parts.append(f"Appointment #{appointment_id}{when}")
    document_type = state.get("document_type")
    if document_type and document_type != "other":
        parts.append(f"{document_type} attached")
    reminder_id = state.get("reminder_id")
    if reminder_id:
        parts.append(f"Reminder #{reminder_id} scheduled")
    if parts:
        return "Done: " + "; ".join(parts) + "."
    return "Request handled."