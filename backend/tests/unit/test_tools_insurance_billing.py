"""Tool tests: insurance lookup + eligibility, billing lookup + explanation."""

import pytest

from app.tools.appointments import book_appointment
from app.tools.billing import generate_billing_explanation, lookup_fee_items
from app.tools.errors import BillingUnavailableError
from app.tools.insurance import check_eligibility, get_active_policy, lookup_insurance
from tests.unit.factories import (
    audit_count,
    make_department,
    make_doctor,
    make_patient,
    make_slot,
    uniq,
)
from app.db.models import BillingExplanation, BillingLineItem, InsuranceEligibilityCheck, InsurancePolicy
from datetime import date


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


def _booked_appointment(db, patient=None):
    if patient is None:
        patient = make_patient(db)
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)
    return book_appointment(db, patient.id, dept.id, doctor.id, slot.id, visit_type="consultation")


def test_insurance_lookup_statuses(db):
    patient = make_patient(db)
    result = lookup_insurance(db, patient.id)
    assert result["status"] == "missing"
    assert "No insurance policy on file" in result["reason"]

    _add_policy(db, patient.id, "ActiveCare", plan_type="silver")
    assert lookup_insurance(db, patient.id)["status"] == "active"
    assert get_active_policy(db, patient.id) is not None

    expired = make_patient(db)
    _add_policy(db, expired.id, "OldCare", valid_from=date(2020, 1, 1), valid_to=date(2021, 12, 31))
    result = lookup_insurance(db, expired.id)
    assert result["status"] == "expired"
    assert get_active_policy(db, expired.id) is None

    inactive = make_patient(db)
    _add_policy(db, inactive.id, "ClosedCare", active=False)
    assert lookup_insurance(db, inactive.id)["status"] == "inactive"
    assert audit_count(db, "insurance.lookup") == 4


def test_eligibility_covered_and_needs_pre_auth(db):
    patient = make_patient(db)
    _add_policy(db, patient.id, "GoldCare", plan_type="gold")
    appt = _booked_appointment(db, patient)
    check = check_eligibility(db, appt.id)
    assert check.status == "covered"
    assert "GoldCare" in check.coverage_summary
    assert "payment guarantee" in check.coverage_summary
    assert audit_count(db, "insurance.eligibility_checked") == 1

    bronze = make_patient(db)
    _add_policy(db, bronze.id, "BronzeCare", plan_type="bronze")
    appt2 = _booked_appointment(db, bronze)
    check2 = check_eligibility(db, appt2.id)
    assert check2.status == "needs_pre_authorization"
    assert "pre-authorization" in check2.coverage_summary


def test_eligibility_not_covered_for_expired_and_missing_policy(db):
    expired = make_patient(db)
    _add_policy(db, expired.id, "OldCare", valid_from=date(2020, 1, 1), valid_to=date(2021, 12, 31))
    appt1 = _booked_appointment(db, expired)
    check1 = check_eligibility(db, appt1.id)
    assert check1.status == "not_covered"
    assert "expired" in check1.coverage_summary

    none = make_patient(db)
    appt2 = _booked_appointment(db, none)
    check2 = check_eligibility(db, appt2.id)
    assert check2.status == "not_covered"
    assert "No insurance policy" in check2.coverage_summary


def test_billing_lookup_and_explanation_from_fee_schedule(db):
    patient = make_patient(db)
    dept = make_department(db)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)
    appt = book_appointment(
        db, patient.id, dept.id, doctor.id, slot.id, visit_type="consultation", reason="Checkup"
    )

    fees = lookup_fee_items(db, dept.id)
    assert len(fees) == 4
    assert audit_count(db, "billing.fee_schedule_lookup") == 1

    explanation = generate_billing_explanation(db, appt.id)
    assert explanation.id is not None
    line_items = (
        db.query(BillingLineItem).filter(BillingLineItem.appointment_id == appt.id).all()
    )
    assert len(line_items) == 2
    assert {i.category for i in line_items} == {"consultation", "facility"}
    assert all(i.source.startswith("fee_schedule:") for i in line_items)
    assert f"{dept.name} consultation" in explanation.summary_text
    assert "$120.00" in explanation.summary_text
    assert "not a legally binding invoice" in explanation.summary_text
    assert "payment" not in explanation.summary_text or "may reduce" in explanation.summary_text
    assert audit_count(db, "billing.explanation_generated") == 1


def test_billing_explanation_varies_by_department(db):
    patient = make_patient(db)
    dept_a = make_department(db)
    dept_b = make_department(db)
    doctor_a = make_doctor(db, dept_a.id)
    doctor_b = make_doctor(db, dept_b.id)

    slot_a = make_slot(db, doctor_a.id, day_offset=10, hour=9)
    slot_b = make_slot(db, doctor_b.id, day_offset=10, hour=9)
    appt_a = book_appointment(db, patient.id, dept_a.id, doctor_a.id, slot_a.id, visit_type="consultation")
    appt_b = book_appointment(db, patient.id, dept_b.id, doctor_b.id, slot_b.id, visit_type="consultation")

    expl_a = generate_billing_explanation(db, appt_a.id)
    expl_b = generate_billing_explanation(db, appt_b.id)
    assert expl_a.summary_text != expl_b.summary_text
    assert dept_a.name in expl_a.summary_text
    assert dept_b.name in expl_b.summary_text
    assert dept_a.name not in expl_b.summary_text


def test_billing_fails_without_fee_schedule(db):
    patient = make_patient(db)
    dept = make_department(db, with_fees=False)
    doctor = make_doctor(db, dept.id)
    slot = make_slot(db, doctor.id)
    appt = book_appointment(db, patient.id, dept.id, doctor.id, slot.id, visit_type="consultation")

    with pytest.raises(BillingUnavailableError):
        generate_billing_explanation(db, appt.id)
    assert audit_count(db, "billing.explanation_generated.failed") == 1