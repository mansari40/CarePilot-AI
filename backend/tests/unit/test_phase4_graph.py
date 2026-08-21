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

    def bind_tools(self, tools, **kwargs):
        self.bound_tools.append([t["function"]["name"] for t in tools])
        return self

    def invoke(self, messages):
        self.seen_messages.append(messages)
        if not self.script:
            raise AssertionError("FakeChatModel ran out of scripted responses")
        return self.script.pop(0)


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


def safe_screen(reason="All good."):
    return ai_with_tool("complete_safety_screen", {"safe": True, "reason": reason})


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
    assert len(booking_tool_messages) == 1


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