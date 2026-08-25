"""Phase 4 tests: specialist nodes, Safety & Escalation screening, conditional
edges, and restart-and-resume.

The LLM is mocked (scripted AIMessage responses) so no live Groq key is needed;
get_llm() itself is only tested for its config behavior.
"""

from datetime import timedelta, timezone

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.core import graph as graph_mod
from app.core.llm import groq_client
from app.core.orchestrator import resume_workflow, start_workflow
from app.core.persistence import get_workflow_run
from app.db.models import Appointment, Escalation, PatientDocument, Reminder
from tests.unit.factories import make_department, make_doctor, make_patient, make_slot


class FakeChatModel:
    """Scripted fake ChatGroq: each invoke returns the next scripted AIMessage."""

    def __init__(self, script):
        self.script = list(script)
        self.seen_messages = []
        self.bound_tools = []
        self._appointment_id = None

    def bind_tools(self, tools, **kwargs):
        self.bound_tools.append([t["function"]["name"] for t in tools])
        return self

    def invoke(self, messages):
        self.seen_messages.append(messages)
        if not self.script:
            raise AssertionError("FakeChatModel ran out of scripted responses")
        msg = self.script.pop(0)
        if isinstance(msg, type) and issubclass(msg, Exception):
            raise msg("Tool call validation failed: attempted to call tool "
                      "'run_insurance_eligibility_check' which was not in request.tools")
        if self._appointment_id is not None:
            msg = _patch_appointment_id(msg, self._appointment_id)
        return msg


class FakeHolder:
    llm = None


def ai_with_tool(name, args, call_id="call_1"):
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}],
    )


def ai_with_tools(calls):
    return AIMessage(
        content="",
        tool_calls=[
            {"name": name, "args": args, "id": call_id, "type": "tool_call"}
            for name, args, call_id in calls
        ],
    )


def ai_text(text="Done."):
    return AIMessage(content=text)


def _patch_appointment_id(msg: AIMessage, appointment_id: int) -> AIMessage:
    """Replace placeholder appointment_id=0 in tool call args with the real id."""
    if not hasattr(msg, "tool_calls") or not msg.tool_calls:
        return msg
    patched_calls = []
    for tc in msg.tool_calls:
        args = dict(tc["args"])
        if args.get("appointment_id") == 0:
            args["appointment_id"] = appointment_id
        patched_calls.append({**tc, "args": args})
    return msg.model_copy(update={"tool_calls": patched_calls})


def safe_screen(reason="All good."):
    return ai_with_tool("complete_safety_screen", {"safe": True, "reason": reason})


def complete_billing(explanation_id=None, cost="150.00"):
    return ai_with_tool(
        "complete_billing",
        {
            "billing_explanation_id": explanation_id,
            "estimated_cost": cost,
            "message": "Billing explanation generated",
        },
    )


def insurance_and_billing_responses(check_id=None, explanation_id=None, cost="150.00"):
    """Return the standard insurance + billing fake responses for Phase 4 tests.

    These call the completion tools directly (skipping lookup tools) so no
    real appointment_id is needed.  Phase 6 tests cover the full flow.
    """
    return [
        ai_with_tool(
            "complete_insurance_check",
            {"insurance_check_id": check_id, "eligibility_status": "covered", "message": "Insurance: covered"},
        ),
        ai_with_tool(
            "complete_billing",
            {"billing_explanation_id": explanation_id, "estimated_cost": cost, "message": "Billing done"},
        ),
    ]


@pytest.fixture
def fake_llm(monkeypatch):
    holder = FakeHolder()
    monkeypatch.setattr(groq_client, "get_llm", lambda fast=False: holder.llm)
    return holder


def make_document(db, patient, filename="ecg_report.pdf") -> PatientDocument:
    doc = PatientDocument(
        patient_id=patient.id,
        filename=filename,
        storage_path=f"/tmp/{filename}",
        document_type="ecg",
        checksum="cafe1234",
        is_duplicate=False,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def _booking_args(patient, dept, doctor, slot) -> dict:
    return {
        "patient_id": patient.id,
        "department_id": dept.id,
        "doctor_id": doctor.id,
        "slot_id": slot.id,
        "visit_type": "follow_up",
        "reason": "Cardiology follow-up",
    }


def _slot_window(slot, dept) -> dict:
    return {
        "from_time": (slot.start_time - timedelta(days=1)).isoformat(),
        "to_time": (slot.start_time + timedelta(days=1)).isoformat(),
        "department_id": dept.id,
    }


def _routing(patient, dept, **flags) -> dict:
    return {
        "department_id": dept.id,
        "clarify_question": None,
        "needs_booking": flags.get("needs_booking", True),
        "needs_document": flags.get("needs_document", False),
        "needs_reminder": flags.get("needs_reminder", False),
    }


def _reminder_args(patient, appointment) -> dict:
    return {
        "patient_id": patient.id,
        "appointment_id": appointment.id,
        "reminder_type": "appointment",
        "scheduled_for": (appointment.scheduled_for - timedelta(days=1)).isoformat(),
        "channel": "in_app",
        "message": "Cardiology follow-up reminder",
    }


def _fresh_graph_after_restart():
    """Simulate a backend restart: drop the cached compiled graph."""
    graph_mod.get_graph.cache_clear()


def test_get_llm_requires_groq_key(monkeypatch):
    from app.config import Settings

    monkeypatch.setattr(groq_client, "get_settings", lambda: Settings(groq_api_key=""))
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        groq_client.get_llm()


def test_get_llm_reads_models_from_settings(monkeypatch):
    from app.config import Settings

    monkeypatch.setattr(
        groq_client,
        "get_settings",
        lambda: Settings(groq_api_key="test-key", groq_model="model-a", groq_model_fast="model-b"),
    )
    llm = groq_client.get_llm()
    fast = groq_client.get_llm(fast=True)
    assert llm.model_name == "model-a"
    assert fast.model_name == "model-b"


def test_safety_screen_escalates_unsafe_request(db, fake_llm):
    patient = make_patient(db)
    fake_llm.llm = FakeChatModel(
        [
            ai_with_tool(
                "create_escalation",
                {
                    "reason": "Patient describes chest pain and asks for treatment advice",
                    "severity": "critical",
                    "details": "Emergency language detected in the request",
                },
            )
        ]
    )

    run = start_workflow(patient.id, "I'm having chest pain, is it a heart attack?")

    assert run.status == "escalated"
    assert run.summary and "chest pain" in run.summary
    escalation = db.query(Escalation).one()
    assert escalation.severity == "critical"
    assert escalation.status == "open"
    assert escalation.workflow_run_id == run.id
    assert escalation.patient_id == patient.id
    assert db.query(Appointment).count() == 0
    checkpoint = graph_mod.get_graph().get_state({"configurable": {"thread_id": run.thread_id}})
    tool_messages = [m for m in checkpoint.values["messages"] if isinstance(m, ToolMessage)]
    assert any("chest pain" in m.content for m in tool_messages)


def test_full_pipeline_books_pauses_resumes_completes(db, fake_llm):
    """Cardiology + ECG + reminder end-to-end with a restart between pause and resume."""
    patient = make_patient(db)
    dept = make_department(db, name="Cardiology")
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)
    doc = make_document(db, patient)

    fake_llm.llm = FakeChatModel(
        [
            safe_screen(),
            ai_with_tool("find_department", {"query": "Cardiology"}),
            ai_with_tool("complete_routing", _routing(patient, dept, needs_document=True, needs_reminder=True)),
            ai_with_tool("list_available_slots", _slot_window(slot, dept)),
            ai_with_tool("book_appointment", _booking_args(patient, dept, doctor, slot)),
            *insurance_and_billing_responses(),
            safe_screen("Booking is safe administrative content."),
        ]
    )

    run = start_workflow(
        patient.id,
        "Book me a cardiology follow-up next week and remind me the day before. My ECG is attached.",
        document_id=doc.id,
    )

    assert run.status == "awaiting_confirmation"
    assert run.current_step == "wait_confirm"
    appointment = db.query(Appointment).one()
    assert appointment.slot_id == slot.id
    db.refresh(slot)
    assert slot.is_booked is True

    _fresh_graph_after_restart()

    fake_llm.llm = FakeChatModel(
        [
            ai_with_tool("get_patient_documents", {"patient_id": patient.id}),
            ai_with_tool("classify_document", {"filename": "ecg_report.pdf"}),
            ai_with_tool(
                "attach_document_to_appointment",
                {"document_id": doc.id, "appointment_id": appointment.id},
            ),
            ai_with_tool("complete_document_check", {"message": "ECG verified and attached"}),
            ai_with_tool("create_reminder", _reminder_args(patient, appointment)),
            ai_with_tool("complete_followup", {"message": "Reminder scheduled"}),
            safe_screen("Final answer is safe administrative content."),
        ]
    )

    resumed = resume_workflow(run.id, "Confirmed — please continue.")

    assert resumed.thread_id == run.thread_id
    assert resumed.status == "completed"
    reminders = db.query(Reminder).all()
    assert len(reminders) == 1
    assert reminders[0].appointment_id == appointment.id
    db.refresh(doc)
    assert doc.appointment_id == appointment.id
    assert db.query(Appointment).count() == 1
    db.refresh(slot)
    assert slot.is_booked is True
    assert resumed.summary == "Request fully handled."
    assert resumed.state["final_response"]
    assert f"Appointment #{appointment.id}" in resumed.state["final_response"]
    assert "ecg" in resumed.state["final_response"]
    assert f"Reminder #{reminders[0].id}" in resumed.state["final_response"]

    resume_input = fake_llm.llm.seen_messages[0]
    assert any(isinstance(m, HumanMessage) and "Confirmed" in m.content for m in resume_input)
    booking_tool_messages = [
        m for m in resume_input if isinstance(m, ToolMessage) and '"slot_id"' in m.content
    ]
    assert len(booking_tool_messages) == 0


def test_malformed_tool_args_retried_and_not_persisted(db, fake_llm):
    patient = make_patient(db)
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)
    good_args = _booking_args(patient, dept, doctor, slot)
    bad_args = dict(good_args, slot_id="not-an-integer")
    fake_llm.llm = FakeChatModel(
        [
            safe_screen(),
            ai_with_tool("find_department", {"query": "Cardiology"}),
            ai_with_tool("complete_routing", _routing(patient, dept)),
            ai_with_tool("book_appointment", bad_args, call_id="call_bad"),
            ai_with_tool("book_appointment", good_args, call_id="call_good"),
            *insurance_and_billing_responses(),
            safe_screen(),
        ]
    )

    run = start_workflow(patient.id, "Book me a follow-up.")

    assert db.query(Appointment).count() == 1
    assert run.status == "awaiting_confirmation"
    bad_turn_input = fake_llm.llm.seen_messages[4]
    assert any(
        isinstance(m, ToolMessage) and "Invalid arguments" in m.content
        for m in bad_turn_input
    )
    assert any('"slot_id"' in m.content for m in bad_turn_input)


def test_tool_error_fed_back_to_llm(db, fake_llm):
    patient = make_patient(db)
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)
    args = _booking_args(patient, dept, doctor, slot)
    fake_llm.llm = FakeChatModel(
        [
            safe_screen(),
            ai_with_tool("find_department", {"query": "Cardiology"}),
            ai_with_tool("complete_routing", _routing(patient, dept)),
            ai_with_tools(
                [
                    ("book_appointment", args, "call_1"),
                    ("book_appointment", args, "call_2"),
                ]
            ),
            *insurance_and_billing_responses(),
            safe_screen(),
        ]
    )

    run = start_workflow(patient.id, "Book me an appointment.")

    assert db.query(Appointment).count() == 1
    assert run.status == "awaiting_confirmation"
    checkpoint = graph_mod.get_graph().get_state({"configurable": {"thread_id": run.thread_id}})
    tool_messages = [
        m for m in checkpoint.values["messages"] if isinstance(m, ToolMessage)
    ]
    assert len(tool_messages) >= 2
    assert any("already" in m.content for m in tool_messages)


def test_three_invalid_turns_fail_run(db, fake_llm):
    patient = make_patient(db)
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)
    args = _booking_args(patient, dept, doctor, slot)
    bad_args = dict(args, slot_id="nope")
    fake_llm.llm = FakeChatModel(
        [
            safe_screen(),
            ai_with_tool("find_department", {"query": "Cardiology"}),
            ai_with_tool("complete_routing", _routing(patient, dept)),
            ai_with_tool("book_appointment", bad_args, call_id="a"),
            ai_with_tool("book_appointment", bad_args, call_id="b"),
            ai_with_tool("book_appointment", bad_args, call_id="c"),
        ]
    )

    run = start_workflow(patient.id, "Book me an appointment.")

    assert run.status == "failed"
    assert run.summary and "human review" in run.summary
    assert db.query(Appointment).count() == 0
    assert len(fake_llm.llm.seen_messages) == 6


def test_ambiguous_department_asks_clarify_then_resumes(db, fake_llm):
    patient = make_patient(db)
    dept = make_department(db, name="Cardiology")
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)
    fake_llm.llm = FakeChatModel(
        [
            safe_screen(),
            ai_with_tool("find_department", {"query": "Cardiology"}),
            ai_with_tool(
                "complete_routing",
                {
                    "department_id": None,
                    "clarify_question": "Did you mean Cardiology or Neurology?",
                    "needs_booking": True,
                    "needs_document": False,
                    "needs_reminder": False,
                },
            ),
            safe_screen("Clarification request is safe."),
        ]
    )

    run = start_workflow(patient.id, "Book me a follow-up — heart or brain, whichever.")

    assert run.status == "awaiting_clarification"
    assert run.summary and "Cardiology or Neurology" in run.summary
    assert db.query(Appointment).count() == 0

    fake_llm.llm = FakeChatModel(
        [
            ai_with_tool("find_department", {"query": "Cardiology"}),
            ai_with_tool("complete_routing", _routing(patient, dept)),
            ai_with_tool("list_available_slots", _slot_window(slot, dept)),
            ai_with_tool("book_appointment", _booking_args(patient, dept, doctor, slot)),
            *insurance_and_billing_responses(),
            safe_screen(),
        ]
    )

    resumed = resume_workflow(run.id, "Cardiology, please.")

    assert resumed.thread_id == run.thread_id
    assert resumed.status == "awaiting_confirmation"
    assert db.query(Appointment).count() == 1


def test_missing_document_waits_then_resumes_with_upload(db, fake_llm):
    patient = make_patient(db)
    dept = make_department(db, name="Cardiology")
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)
    fake_llm.llm = FakeChatModel(
        [
            safe_screen(),
            ai_with_tool("find_department", {"query": "Cardiology"}),
            ai_with_tool("complete_routing", _routing(patient, dept, needs_document=True)),
            ai_with_tool("list_available_slots", _slot_window(slot, dept)),
            ai_with_tool("book_appointment", _booking_args(patient, dept, doctor, slot)),
            *insurance_and_billing_responses(),
            safe_screen(),
        ]
    )

    run = start_workflow(patient.id, "Book a cardiology follow-up — my ECG is required.")

    assert run.status == "awaiting_confirmation"
    appointment = db.query(Appointment).one()

    fake_llm.llm = FakeChatModel(
        [
            ai_with_tool("get_patient_documents", {"patient_id": patient.id}),
            ai_with_tool(
                "complete_document_check",
                {"missing_documents": ["ecg"], "message": "ECG is not on file yet"},
            ),
            safe_screen(),
        ]
    )
    waiting = resume_workflow(run.id, "Confirmed.")
    assert waiting.status == "awaiting_document"
    assert waiting.summary and "ecg" in waiting.summary

    doc = make_document(db, patient)
    fake_llm.llm = FakeChatModel(
        [
            ai_with_tool("get_patient_documents", {"patient_id": patient.id}),
            ai_with_tool(
                "attach_document_to_appointment",
                {"document_id": doc.id, "appointment_id": appointment.id},
            ),
            ai_with_tool("complete_document_check", {"message": "ECG verified and attached"}),
            ai_with_tool("complete_followup", {"message": "No reminder needed"}),
            safe_screen(),
        ]
    )
    completed = resume_workflow(run.id, "Here is my ECG.", document_id=doc.id)

    assert completed.status == "completed"
    db.refresh(doc)
    assert doc.appointment_id == appointment.id


def test_draft_output_screened_before_respond(db, fake_llm):
    """The Safety gate screens the final draft and escalates instead of responding."""
    patient = make_patient(db)
    dept = make_department(db)
    fake_llm.llm = FakeChatModel(
        [
            safe_screen(),
            ai_with_tool("find_department", {"query": "Cardiology"}),
            ai_with_tool(
                "complete_routing",
                _routing(patient, dept, needs_booking=False, needs_document=False, needs_reminder=False),
            ),
            ai_with_tool("complete_document_check", {"message": "No documents required"}),
            ai_with_tool("complete_followup", {"message": "No reminder needed"}),
            ai_with_tool(
                "create_escalation",
                {
                    "reason": "Draft answer contains prescription-like content",
                    "severity": "high",
                    "details": "The follow-up agent drafted medication instructions",
                },
            ),
        ]
    )

    run = start_workflow(patient.id, "Set up a follow-up for my appointment.")

    assert run.status == "escalated"
    escalation = db.query(Escalation).one()
    assert escalation.workflow_run_id == run.id
    assert escalation.severity == "high"
    checkpoint = graph_mod.get_graph().get_state({"configurable": {"thread_id": run.thread_id}})
    assert any(
        isinstance(m, ToolMessage) and "prescription" in m.content
        for m in checkpoint.values["messages"]
    )


def test_no_slots_continues_without_booking(db, fake_llm):
    patient = make_patient(db)
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)
    fake_llm.llm = FakeChatModel(
        [
            safe_screen(),
            ai_with_tool("find_department", {"query": "Cardiology"}),
            ai_with_tool("complete_routing", _routing(patient, dept)),
            ai_with_tool("list_available_slots", _slot_window(slot, dept)),
            ai_with_tool(
                "complete_appointment",
                {"appointment_id": None, "message": "No slot is available this week"},
            ),
            ai_with_tool("complete_document_check", {"message": "No documents required"}),
            ai_with_tool("complete_followup", {"message": "No reminder needed"}),
            safe_screen(),
        ]
    )

    run = start_workflow(patient.id, "Book me an appointment, any slot.")

    assert run.status == "completed"
    assert run.summary == "Request fully handled."
    assert db.query(Appointment).count() == 0
    checkpoint = graph_mod.get_graph().get_state({"configurable": {"thread_id": run.thread_id}})
    assert any(
        isinstance(m, ToolMessage) and "No slot is available" in m.content
        for m in checkpoint.values["messages"]
    )


def test_each_node_sees_only_its_own_tools(db, fake_llm):
    patient = make_patient(db)
    dept = make_department(db, name="Cardiology")
    doc = make_document(db, patient)
    fake_llm.llm = FakeChatModel(
        [
            safe_screen(),
            ai_with_tool("find_department", {"query": "Cardiology"}),
            ai_with_tool(
                "complete_routing", _routing(patient, dept, needs_document=True, needs_booking=False)
            ),
            ai_with_tool("get_patient_documents", {"patient_id": patient.id}),
            ai_with_tool("classify_document", {"filename": "ecg_report.pdf"}),
            ai_with_tool(
                "complete_document_check",
                {"document_id": doc.id, "message": "ECG verified on file"},
            ),
            ai_with_tool("complete_followup", {"message": "No reminder needed"}),
            safe_screen(),
        ]
    )

    run = start_workflow(patient.id, "Cardiology follow-up, ECG on file.")

    assert run.status == "completed"
    assert run.summary == "Request fully handled."

    bound = fake_llm.llm.bound_tools
    safety_names = {"complete_safety_screen", "create_escalation", "log_audit_event"}
    routing_names = {"find_department", "complete_routing"}
    document_names = {
        "get_patient_documents",
        "classify_document",
        "attach_document_to_appointment",
        "complete_document_check",
    }
    followup_names = {"create_reminder", "complete_followup"}
    appointment_names = {
        "list_available_slots",
        "book_appointment",
        "reschedule_appointment",
        "cancel_appointment",
        "get_appointment",
        "complete_appointment",
    }

    assert set(bound[0]) == safety_names
    assert set(bound[1]) == routing_names
    assert set(bound[2]) == routing_names
    assert set(bound[3]) == document_names
    assert set(bound[4]) == document_names
    assert set(bound[5]) == document_names
    assert set(bound[6]) == followup_names
    assert set(bound[7]) == safety_names
    assert appointment_names not in [set(b) for b in bound]


def test_llm_rests_then_continues_until_completion(db, fake_llm):
    patient = make_patient(db)
    dept = make_department(db)
    fake_llm.llm = FakeChatModel(
        [
            ai_text("One moment."),
            safe_screen(),
            ai_with_tool("find_department", {"query": "Cardiology"}),
            ai_with_tool(
                "complete_routing",
                _routing(patient, dept, needs_booking=False, needs_document=False, needs_reminder=False),
            ),
            ai_with_tool("complete_document_check", {"message": "No documents required"}),
            ai_with_tool("complete_followup", {"message": "No reminder needed"}),
            safe_screen(),
        ]
    )

    run = start_workflow(patient.id, "Anything for my next appointment?")

    assert run.status == "completed"
    assert len(fake_llm.llm.seen_messages) == 7
    safety_retry_input = fake_llm.llm.seen_messages[1]
    assert any(
        isinstance(m, HumanMessage) and "not complete" in m.content
        for m in safety_retry_input
    )


# ---------------------------------------------------------------------------
# Emergency-vs-routing calibration tests (SAFETY_ENTRY_PROMPT fix)
# ---------------------------------------------------------------------------


def test_emergency_chest_pain_still_escalates(db, fake_llm):
    """Chest pain with urgency = genuine emergency → must escalate."""
    patient = make_patient(db)
    fake_llm.llm = FakeChatModel(
        [
            ai_with_tool(
                "create_escalation",
                {
                    "reason": "Patient reports chest pain — emergency symptom requiring immediate medical attention",
                    "severity": "critical",
                    "details": "Emergency language detected: chest pain with urgent presentation",
                },
            ),
            ai_with_tool(
                "complete_safety_screen",
                {"safe": False, "reason": "Chest pain is a red-flag emergency symptom"},
            ),
        ]
    )

    run = start_workflow(
        patient.id,
        "I have a chest pain and want to see a doctor asap",
    )

    assert run.status == "escalated"
    escalation = db.query(Escalation).one()
    assert escalation.severity == "critical"
    assert escalation.status == "open"
    assert db.query(Appointment).count() == 0


def test_mild_headache_routes_normally(db, fake_llm):
    """Mentioning a light headache as reason for booking → administrative routing, not escalation."""
    patient = make_patient(db)
    dept = make_department(db, name="General Medicine")
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)

    fake_llm.llm = FakeChatModel(
        [
            # Safety screen: headache as booking reason is safe
            safe_screen("Headache mentioned as reason for appointment — administrative routing info, not emergency."),
            # Routing agent: map to General Medicine
            ai_with_tool("find_department", {"query": "General Medicine"}),
            ai_with_tool("complete_routing", _routing(patient, dept)),
            # Appointment agent: book a slot
            ai_with_tool("list_available_slots", _slot_window(slot, dept)),
            ai_with_tool("book_appointment", _booking_args(patient, dept, doctor, slot)),
            # Insurance + billing
            *insurance_and_billing_responses(),
            # Safety gate before confirm
            safe_screen("Booking confirmation is safe administrative content."),
        ]
    )

    run = start_workflow(
        patient.id,
        "i have a light headache and want an appointment",
    )

    assert run.status == "awaiting_confirmation"
    appointment = db.query(Appointment).one()
    assert appointment.slot_id == slot.id
    assert appointment.department_id == dept.id
    db.refresh(slot)
    assert slot.is_booked is True
    # No escalation should exist
    assert db.query(Escalation).count() == 0


def test_skin_rash_routes_to_dermatology(db, fake_llm):
    """Mentioning a skin rash as reason for booking → route to Dermatology, not escalation."""
    patient = make_patient(db)
    dept = make_department(db, name="Dermatology")
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)

    fake_llm.llm = FakeChatModel(
        [
            # Safety screen: skin rash as booking reason is safe
            safe_screen("Skin rash mentioned as reason for appointment — administrative routing to Dermatology."),
            # Routing agent: map to Dermatology
            ai_with_tool("find_department", {"query": "Dermatology"}),
            ai_with_tool("complete_routing", _routing(patient, dept)),
            # Appointment agent: book a slot
            ai_with_tool("list_available_slots", _slot_window(slot, dept)),
            ai_with_tool("book_appointment", _booking_args(patient, dept, doctor, slot)),
            # Insurance + billing
            *insurance_and_billing_responses(),
            # Safety gate before confirm
            safe_screen("Booking confirmation is safe administrative content."),
        ]
    )

    run = start_workflow(
        patient.id,
        "i have a skin rush and want an appointment",
    )

    assert run.status == "awaiting_confirmation"
    appointment = db.query(Appointment).one()
    assert appointment.slot_id == slot.id
    assert appointment.department_id == dept.id
    db.refresh(slot)
    assert slot.is_booked is True
    # No escalation should exist
    assert db.query(Escalation).count() == 0


def test_reminder_message_matches_real_appointment_time(db):
    """Reminder message must always reflect the real appointment time, not hallucinated."""
    from datetime import datetime
    from app.db.models import Appointment
    from app.tools.reminders import _build_reminder_message

    patient = make_patient(db)
    dept = make_department(db, name="Cardiology")
    doctor = make_doctor(db, department_id=dept.id)
    appt_time = datetime(2026, 8, 24, 11, 0, tzinfo=timezone.utc)
    appt = Appointment(
        patient_id=patient.id,
        department_id=dept.id,
        doctor_id=doctor.id,
        status="confirmed",
        visit_type="follow_up",
        scheduled_for=appt_time,
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    msg = _build_reminder_message(appt, db)
    assert "11:00 AM" in msg
    assert "August 24, 2026" in msg
    assert doctor.name in msg
    assert "Cardiology" in msg

    appt_time_2 = datetime(2026, 9, 1, 9, 30, tzinfo=timezone.utc)
    appt2 = Appointment(
        patient_id=patient.id,
        department_id=dept.id,
        doctor_id=doctor.id,
        status="confirmed",
        visit_type="consultation",
        scheduled_for=appt_time_2,
    )
    db.add(appt2)
    db.commit()
    db.refresh(appt2)

    msg2 = _build_reminder_message(appt2, db)
    assert "9:30 AM" in msg2
    assert "September 01, 2026" in msg2
    assert "Cardiology" in msg2


def test_create_reminder_auto_generates_message_when_omitted(db):
    """When LLM omits message, create_reminder builds it from real appointment data."""
    from datetime import datetime
    from app.db.models import Appointment
    from app.tools.reminders import create_reminder

    patient = make_patient(db)
    dept = make_department(db, name="Neurology")
    doctor = make_doctor(db, department_id=dept.id)
    appt_time = datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)
    appt = Appointment(
        patient_id=patient.id,
        department_id=dept.id,
        doctor_id=doctor.id,
        status="confirmed",
        scheduled_for=appt_time,
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    reminder = create_reminder(
        db, patient_id=patient.id, appointment_id=appt.id, message=None,
    )
    assert "2:00 PM" in reminder.message
    assert "October 15, 2026" in reminder.message
    assert "Neurology" in reminder.message


# ---------------------------------------------------------------------------
# LLM invocation error handling (tool validation failures)
# ---------------------------------------------------------------------------


def test_llm_tool_validation_error_retries_then_succeeds(db, fake_llm):
    """When the LLM raises a tool-validation error (e.g. hallucinated tool name),
    the node catches it, feeds the error back, and retries until success."""
    patient = make_patient(db)
    dept = make_department(db, name="Cardiology")
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)

    class ToolValidationError(Exception):
        pass

    fake_llm.llm = FakeChatModel(
        [
            safe_screen(),
            ai_with_tool("find_department", {"query": "Cardiology"}),
            ai_with_tool("complete_routing", _routing(patient, dept)),
            ai_with_tool("list_available_slots", _slot_window(slot, dept)),
            ai_with_tool("book_appointment", _booking_args(patient, dept, doctor, slot)),
            # Insurance node: first call raises tool validation error (simulates Groq 400)
            ToolValidationError,
            # Retry: insurance node succeeds with correct tool
            ai_with_tool(
                "complete_insurance_check",
                {"insurance_check_id": None, "eligibility_status": "covered", "message": "Insurance: covered"},
            ),
            ai_with_tool(
                "complete_billing",
                {"billing_explanation_id": None, "estimated_cost": "150.00", "message": "Billing done"},
            ),
            safe_screen("All safe."),
        ]
    )

    run = start_workflow(patient.id, "Book me a cardiology appointment.")

    assert run.status == "awaiting_confirmation"
    assert run.current_step == "wait_confirm"
    appointment = db.query(Appointment).one()
    assert appointment.slot_id == slot.id


def test_llm_tool_validation_error_fails_after_max_attempts(db, fake_llm):
    """After MAX_FAILED_ATTEMPTS consecutive LLM errors, the run is marked failed."""
    patient = make_patient(db)
    dept = make_department(db, name="Cardiology")
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)

    class ToolValidationError(Exception):
        pass

    fake_llm.llm = FakeChatModel(
        [
            safe_screen(),
            ai_with_tool("find_department", {"query": "Cardiology"}),
            ai_with_tool("complete_routing", _routing(patient, dept)),
            ai_with_tool("list_available_slots", _slot_window(slot, dept)),
            ai_with_tool("book_appointment", _booking_args(patient, dept, doctor, slot)),
            # Insurance node: 3 consecutive LLM errors
            ToolValidationError,
            ToolValidationError,
            ToolValidationError,
        ]
    )

    run = start_workflow(patient.id, "Book me a cardiology appointment.")

    assert run.status == "failed"
    assert run.summary and "human review" in run.summary
    assert db.query(Appointment).count() == 1


def test_retry_after_llm_error_does_not_duplicate_appointments(db, fake_llm):
    """When the insurance node fails then retries, no duplicate appointments are created."""
    patient = make_patient(db)
    dept = make_department(db, name="Cardiology")
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)

    class ToolValidationError(Exception):
        pass

    fake_llm.llm = FakeChatModel(
        [
            safe_screen(),
            ai_with_tool("find_department", {"query": "Cardiology"}),
            ai_with_tool("complete_routing", _routing(patient, dept)),
            ai_with_tool("list_available_slots", _slot_window(slot, dept)),
            ai_with_tool("book_appointment", _booking_args(patient, dept, doctor, slot)),
            # Insurance node: first call fails, retry succeeds
            ToolValidationError,
            ai_with_tool(
                "complete_insurance_check",
                {"insurance_check_id": None, "eligibility_status": "covered", "message": "Insurance: covered"},
            ),
            ai_with_tool(
                "complete_billing",
                {"billing_explanation_id": None, "estimated_cost": "150.00", "message": "Billing done"},
            ),
            safe_screen("All safe."),
        ]
    )

    run = start_workflow(patient.id, "Book me a cardiology appointment.")

    assert run.status == "awaiting_confirmation"
    assert db.query(Appointment).count() == 1
    appointment = db.query(Appointment).one()
    assert appointment.slot_id == slot.id


def test_cardiology_appointment_no_document_request_skips_document(db, fake_llm):
    """Regression: cardiology appointment without explicit document mention must NOT
    enter awaiting_document or request ECG.

    The user said: 'I need an appointment with cardiology department next week'.
    This should flow: safety → routing → book → insurance → billing → safety_gate → wait_confirm.
    On resume it should immediately complete the document step with 'No documents required'.
    """
    patient = make_patient(db)
    dept = make_department(db, name="Cardiology")
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)

    fake_llm.llm = FakeChatModel(
        [
            safe_screen(),
            ai_with_tool("find_department", {"query": "Cardiology"}),
            ai_with_tool("complete_routing", _routing(patient, dept)),
            ai_with_tool("list_available_slots", _slot_window(slot, dept)),
            ai_with_tool("book_appointment", _booking_args(patient, dept, doctor, slot)),
            *insurance_and_billing_responses(),
            safe_screen("Booking is safe."),
        ]
    )

    run = start_workflow(patient.id, "I need an appointment with cardiology department next week")

    assert run.status == "awaiting_confirmation"
    assert run.current_step == "wait_confirm"
    assert db.query(Appointment).count() == 1

    _fresh_graph_after_restart()

    fake_llm.llm = FakeChatModel(
        [
            ai_with_tool("create_reminder", _reminder_args(patient, db.query(Appointment).one())),
            ai_with_tool("complete_followup", {"message": "Reminder scheduled"}),
            safe_screen("Final answer is safe."),
        ]
    )

    resumed = resume_workflow(run.id, "Confirmed — please continue.")

    assert resumed.status == "completed"
    assert resumed.summary == "Request fully handled."
    assert db.query(Appointment).count() == 1
    appointment = db.query(Appointment).one()
    assert appointment.slot_id == slot.id

    checkpoint = graph_mod.get_graph().get_state(
        {"configurable": {"thread_id": resumed.thread_id}}
    )
    all_messages = checkpoint.values.get("messages", [])
    tool_messages = [m for m in all_messages if isinstance(m, ToolMessage)]

    state_vals = checkpoint.values
    assert state_vals.get("missing_documents") == [], (
        "missing_documents should be empty when user did not mention documents"
    )
    assert not any("ecg" in m.content.lower() for m in tool_messages), (
        "ECG should not be requested when the user did not mention documents"
    )


def test_explicit_document_request_still_pauses_for_document(db, fake_llm):
    """Genuinely document-required workflows should still pause at awaiting_document.

    The user said: 'I need a cardiology appointment next week. My ECG report is attached.'
    This explicitly mentions an ECG, so needs_document=true and the document step should run.
    """
    patient = make_patient(db)
    dept = make_department(db, name="Cardiology")
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)
    doc = make_document(db, patient)

    fake_llm.llm = FakeChatModel(
        [
            safe_screen(),
            ai_with_tool("find_department", {"query": "Cardiology"}),
            ai_with_tool(
                "complete_routing",
                _routing(patient, dept, needs_document=True),
            ),
            ai_with_tool("list_available_slots", _slot_window(slot, dept)),
            ai_with_tool("book_appointment", _booking_args(patient, dept, doctor, slot)),
            *insurance_and_billing_responses(),
            safe_screen("Booking is safe."),
        ]
    )

    run = start_workflow(
        patient.id,
        "I need a cardiology appointment next week. My ECG report is attached.",
        document_id=doc.id,
    )

    assert run.status == "awaiting_confirmation"

    _fresh_graph_after_restart()

    fake_llm.llm = FakeChatModel(
        [
            ai_with_tool("get_patient_documents", {"patient_id": patient.id}),
            ai_with_tool("classify_document", {"filename": "ecg_report.pdf"}),
            ai_with_tool(
                "attach_document_to_appointment",
                {"document_id": doc.id, "appointment_id": db.query(Appointment).one().id},
            ),
            ai_with_tool("complete_document_check", {"message": "ECG verified"}),
            ai_with_tool("create_reminder", _reminder_args(patient, db.query(Appointment).one())),
            ai_with_tool("complete_followup", {"message": "Reminder scheduled"}),
            safe_screen("Final answer is safe."),
        ]
    )

    resumed = resume_workflow(run.id, "Confirmed — please continue.")

    assert resumed.status == "completed"
    db.refresh(doc)
    assert doc.appointment_id == db.query(Appointment).one().id


# ---------------------------------------------------------------------------
# Timeout safety tests
# ---------------------------------------------------------------------------

import time as _time

from app.config import Settings
from app.core import orchestrator as orch_mod
from app.core.orchestrator import WorkflowTimeoutError


class SlowFakeChatModel:
    """Fake LLM whose invoke() sleeps, simulating a hung Groq connection."""

    def __init__(self, delay: float = 999):
        self.delay = delay
        self.call_count = 0

    def bind_tools(self, tools, **kwargs):
        return self

    def invoke(self, messages):
        self.call_count += 1
        _time.sleep(self.delay)
        raise AssertionError("Should never reach here — timeout should fire first")


def test_start_workflow_times_out_cleanly(db, fake_llm, monkeypatch):
    """A hung LLM causes start_workflow to fail within the configured timeout."""
    patient = make_patient(db)
    fake_llm.llm = SlowFakeChatModel(delay=999)

    # Set a very short workflow timeout so the test runs fast.
    monkeypatch.setattr(orch_mod, "get_settings", lambda: Settings(
        groq_api_key="test",
        workflow_timeout=2,
    ))

    t0 = _time.monotonic()
    run = start_workflow(patient.id, "I need a cardiology appointment")
    elapsed = _time.monotonic() - t0

    assert run.status == "failed"
    assert "too long" in run.state["error"]
    # Must complete well within 10 s even with the 2 s timeout + overhead.
    assert elapsed < 10, f"start_workflow took {elapsed:.1f}s — likely hung"


def test_resume_workflow_times_out_cleanly(db, fake_llm, monkeypatch):
    """A hung LLM causes resume_workflow to fail within the configured timeout."""
    patient = make_patient(db)
    dept = make_department(db, name="Cardiology")
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)

    # First: run a normal workflow that pauses at awaiting_confirmation.
    fake_llm.llm = FakeChatModel(
        [
            safe_screen(),
            ai_with_tool("find_department", {"query": "Cardiology"}),
            ai_with_tool("complete_routing", _routing(patient, dept)),
            ai_with_tool("list_available_slots", _slot_window(slot, dept)),
            ai_with_tool("book_appointment", _booking_args(patient, dept, doctor, slot)),
        ]
    )
    run = start_workflow(patient.id, "Cardiology appointment")
    assert run.status == "awaiting_confirmation"

    # Now inject a slow fake for the resume path.
    fake_llm.llm = SlowFakeChatModel(delay=999)
    monkeypatch.setattr(orch_mod, "get_settings", lambda: Settings(
        groq_api_key="test",
        workflow_timeout=2,
    ))

    t0 = _time.monotonic()
    resumed = resume_workflow(run.id, "confirmed")
    elapsed = _time.monotonic() - t0

    assert resumed.status == "failed"
    assert "too long" in resumed.state["error"]
    assert elapsed < 10, f"resume_workflow took {elapsed:.1f}s — likely hung"


def test_groq_timeout_setting_applied(monkeypatch):
    """ChatGroq receives the configured groq_timeout."""
    from unittest.mock import patch as _patch

    from langchain_groq import ChatGroq

    captured_kwargs = {}

    original_init = ChatGroq.__init__

    def capturing_init(self, *args, **kwargs):
        captured_kwargs.update(kwargs)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(orch_mod, "get_settings", lambda: Settings(
        groq_api_key="test-key",
        groq_timeout=99,
    ))
    monkeypatch.setattr(ChatGroq, "__init__", capturing_init)

    llm = groq_client.get_llm()
    assert captured_kwargs.get("timeout") == 99