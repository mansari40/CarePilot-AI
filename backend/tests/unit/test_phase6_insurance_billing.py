"""Phase 6 tests: Insurance Eligibility and Billing agents in the graph.

Graph-level tests verify routing and state transitions with fake LLMs calling
only completion tools (the real tool behavior is covered by tool-level tests
in test_tools_insurance_billing.py).

Tool-level tests verify that eligibility checks are grounded in real policy
data and that billing line items vary by department.
"""

from datetime import date

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from app.core import graph as graph_mod
from app.core.llm import groq_client
from app.core.orchestrator import resume_workflow, start_workflow
from app.core.tools import BILLING_TOOLS, INSURANCE_TOOLS
from app.db.models import (
    Appointment,
    BillingExplanation,
    BillingLineItem,
    InsuranceEligibilityCheck,
    InsurancePolicy,
)
from tests.unit.factories import make_department, make_doctor, make_patient, make_slot, uniq


class FakeChatModel:
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


def safe_screen(reason="All good."):
    return ai_with_tool("complete_safety_screen", {"safe": True, "reason": reason})


def _routing(patient, dept, **overrides):
    return {
        "department_id": dept.id,
        "clarify_question": None,
        "needs_booking": True,
        "needs_document": False,
        "needs_reminder": False,
        **overrides,
    }


def _slot_window(slot, dept):
    from datetime import timedelta
    return {
        "from_time": (slot.start_time - timedelta(days=1)).isoformat(),
        "to_time": (slot.end_time + timedelta(days=14)).isoformat(),
        "department_id": dept.id,
    }


def _booking_args(patient, dept, doctor, slot):
    return {
        "patient_id": patient.id,
        "department_id": dept.id,
        "doctor_id": doctor.id,
        "slot_id": slot.id,
        "visit_type": "consultation",
        "reason": "Follow-up",
    }


def _add_policy(db, patient_id, provider, plan_type="silver", active=True, valid_from=None, valid_to=None):
    policy = InsurancePolicy(
        patient_id=patient_id,
        provider_name=provider,
        policy_number=uniq("POL"),
        plan_type=plan_type,
        active=active,
        valid_from=valid_from or date(2024, 1, 1),
        valid_to=valid_to or date(2099, 12, 31),
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


@pytest.fixture
def fake_llm(monkeypatch):
    holder = FakeHolder()
    monkeypatch.setattr(groq_client, "get_llm", lambda fast=False: holder.llm)
    return holder


def _graph_script(patient, dept, doctor, slot, insurance_status="covered", billing_cost="160.00"):
    return [
        safe_screen(),
        ai_with_tool("find_department", {"query": "Cardiology"}),
        ai_with_tool("complete_routing", _routing(patient, dept)),
        ai_with_tool("list_available_slots", _slot_window(slot, dept)),
        ai_with_tool("book_appointment", _booking_args(patient, dept, doctor, slot)),
        ai_with_tool(
            "complete_insurance_check",
            {"insurance_check_id": None, "eligibility_status": insurance_status, "message": f"Insurance: {insurance_status}"},
        ),
        ai_with_tool(
            "complete_billing",
            {"billing_explanation_id": None, "estimated_cost": billing_cost, "message": "Billing done"},
        ),
        safe_screen("All output is safe administrative content."),
    ]


def _get_graph_state(run):
    checkpoint = graph_mod.get_graph().get_state({"configurable": {"thread_id": run.thread_id}})
    return checkpoint.values


# ─── Graph topology: insurance → billing → safety_before_confirm ───


def test_graph_routes_through_insurance_and_billing(db, fake_llm):
    patient = make_patient(db)
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)

    fake_llm.llm = FakeChatModel(_graph_script(patient, dept, doctor, slot))

    run = start_workflow(patient.id, "Book me a cardiology appointment.")
    assert run.status == "awaiting_confirmation"
    assert run.current_step == "wait_confirm"

    state = _get_graph_state(run)
    tool_names = [
        m.tool_calls[0]["name"]
        for m in state["messages"]
        if hasattr(m, "tool_calls") and m.tool_calls
    ]
    assert "complete_insurance_check" in tool_names
    assert "complete_billing" in tool_names


def test_insurance_covered_status_set_in_state(db, fake_llm):
    patient = make_patient(db)
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)

    fake_llm.llm = FakeChatModel(_graph_script(patient, dept, doctor, slot, insurance_status="covered"))

    run = start_workflow(patient.id, "Book me a cardiology appointment.")
    state = _get_graph_state(run)
    assert state["eligibility_status"] == "covered"


def test_insurance_needs_preauthorization_status_set_in_state(db, fake_llm):
    patient = make_patient(db)
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)

    fake_llm.llm = FakeChatModel(_graph_script(patient, dept, doctor, slot, insurance_status="needs_preauthorization"))

    run = start_workflow(patient.id, "Book me a cardiology appointment.")
    state = _get_graph_state(run)
    assert state["eligibility_status"] == "needs_preauthorization"


def test_insurance_no_policy_status_set_in_state(db, fake_llm):
    patient = make_patient(db)
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)

    fake_llm.llm = FakeChatModel(_graph_script(patient, dept, doctor, slot, insurance_status="no_policy"))

    run = start_workflow(patient.id, "Book me a cardiology appointment.")
    state = _get_graph_state(run)
    assert state["eligibility_status"] == "no_policy"


def test_billing_estimated_cost_set_in_state(db, fake_llm):
    patient = make_patient(db)
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)

    fake_llm.llm = FakeChatModel(_graph_script(patient, dept, doctor, slot, billing_cost="250.50"))

    run = start_workflow(patient.id, "Book me a cardiology appointment.")
    state = _get_graph_state(run)
    assert state["estimated_cost"] == "250.50"


def test_tool_scoping_insurance_node_only_sees_insurance_tools(db):
    expected_names = {t.name for t in INSURANCE_TOOLS}
    assert "lookup_insurance" in expected_names
    assert "check_eligibility" in expected_names
    assert "complete_insurance_check" in expected_names
    assert "book_appointment" not in expected_names
    assert "generate_billing_explanation" not in expected_names


def test_tool_scoping_billing_node_only_sees_billing_tools(db):
    expected_names = {t.name for t in BILLING_TOOLS}
    assert "lookup_fee_items" in expected_names
    assert "generate_billing_explanation" in expected_names
    assert "complete_billing" in expected_names
    assert "book_appointment" not in expected_names
    assert "lookup_insurance" not in expected_names


# ─── Criterion 1: Eligibility grounded in real policy data (tool-level) ───


def test_active_gold_policy_produces_covered(db):
    from app.tools.appointments import book_appointment
    from app.tools.insurance import check_eligibility

    patient = make_patient(db)
    _add_policy(db, patient.id, "GoldCare", plan_type="gold")
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)
    appt = book_appointment(db, patient.id, dept.id, doctor.id, slot.id, visit_type="consultation")
    check = check_eligibility(db, appt.id)
    assert check.status == "covered"
    assert "GoldCare" in check.coverage_summary
    assert "not a payment guarantee" in check.coverage_summary.lower()


def test_bronze_plan_produces_needs_preauthorization(db):
    from app.tools.appointments import book_appointment
    from app.tools.insurance import check_eligibility

    patient = make_patient(db)
    _add_policy(db, patient.id, "BronzeCare", plan_type="bronze")
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)
    appt = book_appointment(db, patient.id, dept.id, doctor.id, slot.id, visit_type="procedure")
    check = check_eligibility(db, appt.id)
    assert check.status == "needs_pre_authorization"
    assert "pre-authorization" in check.coverage_summary.lower()


def test_expired_policy_produces_not_covered(db):
    from app.tools.appointments import book_appointment
    from app.tools.insurance import check_eligibility

    patient = make_patient(db)
    _add_policy(db, patient.id, "OldCare", valid_from=date(2020, 1, 1), valid_to=date(2021, 12, 31))
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)
    appt = book_appointment(db, patient.id, dept.id, doctor.id, slot.id, visit_type="consultation")
    check = check_eligibility(db, appt.id)
    assert check.status == "not_covered"
    assert "expired" in check.coverage_summary.lower()


def test_missing_policy_produces_not_covered(db):
    from app.tools.appointments import book_appointment
    from app.tools.insurance import check_eligibility

    patient = make_patient(db)
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)
    appt = book_appointment(db, patient.id, dept.id, doctor.id, slot.id, visit_type="consultation")
    check = check_eligibility(db, appt.id)
    assert check.status == "not_covered"
    assert "No insurance policy" in check.coverage_summary


# ─── Criterion 2: Billing varies by department ───


def test_billing_explanation_varies_by_department(db):
    from app.tools.appointments import book_appointment
    from app.tools.billing import generate_billing_explanation

    patient = make_patient(db)
    dept_a = make_department(db, name="Cardiology")
    dept_b = make_department(db, name="Neurology")
    doctor_a = make_doctor(db, dept_a.id)
    doctor_b = make_doctor(db, dept_b.id)
    slot_a = make_slot(db, doctor_a.id, day_offset=10)
    slot_b = make_slot(db, doctor_b.id, day_offset=11)

    appt_a = book_appointment(db, patient.id, dept_a.id, doctor_a.id, slot_a.id, visit_type="consultation")
    appt_b = book_appointment(db, patient.id, dept_b.id, doctor_b.id, slot_b.id, visit_type="consultation")

    expl_a = generate_billing_explanation(db, appt_a.id)
    expl_b = generate_billing_explanation(db, appt_b.id)

    assert expl_a.summary_text != expl_b.summary_text
    assert dept_a.name in expl_a.summary_text
    assert dept_b.name in expl_b.summary_text
    assert dept_a.name not in expl_b.summary_text
    assert dept_b.name not in expl_a.summary_text

    items_a = db.query(BillingLineItem).filter(BillingLineItem.appointment_id == appt_a.id).all()
    items_b = db.query(BillingLineItem).filter(BillingLineItem.appointment_id == appt_b.id).all()
    desc_a = {i.description for i in items_a}
    desc_b = {i.description for i in items_b}
    assert desc_a != desc_b
    assert any(dept_a.name in d for d in desc_a)
    assert any(dept_b.name in d for d in desc_b)


# ─── Criterion 3: No payment guarantee, no diagnosis, no legally binding invoice ───


def test_insurance_summary_not_guarantee(db):
    from app.tools.appointments import book_appointment
    from app.tools.insurance import check_eligibility

    patient = make_patient(db)
    _add_policy(db, patient.id, "GoldCare", plan_type="gold")
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)
    appt = book_appointment(db, patient.id, dept.id, doctor.id, slot.id, visit_type="consultation")
    check = check_eligibility(db, appt.id)
    summary = check.coverage_summary.lower()
    assert "guarantee" not in summary or "not a" in summary
    assert "diagnosis" not in summary


def test_billing_explanation_is_estimate_not_invoice(db):
    from app.tools.appointments import book_appointment
    from app.tools.billing import generate_billing_explanation

    patient = make_patient(db)
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)
    appt = book_appointment(db, patient.id, dept.id, doctor.id, slot.id, visit_type="consultation")
    expl = generate_billing_explanation(db, appt.id)
    text = expl.summary_text.lower()
    assert "estimate" in text
    assert "not a legally binding invoice" in text
