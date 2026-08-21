"""Insurance tool — policy lookup and eligibility pre-checks with real rules.

Eligibility is a deterministic rule over persisted policy + visit data, and never
guarantees payment.
"""

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.db.models import Appointment, InsuranceEligibilityCheck, InsurancePolicy, PatientProfile
from app.tools.audit import log_audit
from app.tools.errors import AppointmentNotFoundError, PatientNotFoundError


def get_active_policy(
    session: Session, patient_id: int, actor_user_id: int | None = None
) -> InsurancePolicy | None:
    today = date.today()
    policy = (
        session.query(InsurancePolicy)
        .filter(
            InsurancePolicy.patient_id == patient_id,
            InsurancePolicy.active.is_(True),
            InsurancePolicy.valid_from <= today,
            InsurancePolicy.valid_to >= today,
        )
        .first()
    )
    log_audit(
        session,
        "insurance.policy_lookup",
        "InsurancePolicy",
        entity_id=policy.id if policy else None,
        details={"patient_id": patient_id, "found": policy is not None},
        actor_user_id=actor_user_id,
    )
    session.commit()
    return policy


def lookup_insurance(
    session: Session, patient_id: int, actor_user_id: int | None = None
) -> dict:
    """Describe a patient's insurance situation: active / expired / inactive / missing."""
    policies = (
        session.query(InsurancePolicy)
        .filter(InsurancePolicy.patient_id == patient_id)
        .order_by(InsurancePolicy.created_at.desc())
        .all()
    )
    today = date.today()

    def describe(policy: InsurancePolicy) -> dict:
        if not policy.active:
            return {"status": "inactive", "reason": f"Policy {policy.policy_number} is marked inactive"}
        if policy.valid_to < today:
            return {"status": "expired", "reason": f"Policy {policy.policy_number} expired on {policy.valid_to}"}
        if policy.valid_from > today:
            return {"status": "not_yet_valid", "reason": f"Policy {policy.policy_number} starts on {policy.valid_from}"}
        return {"status": "active", "reason": "Policy is currently active and valid"}

    if not policies:
        result = {"patient_id": patient_id, "status": "missing", "reason": "No insurance policy on file"}
    else:
        newest = policies[0]
        result = {
            "patient_id": patient_id,
            "policy_id": newest.id,
            "provider_name": newest.provider_name,
            "plan_type": newest.plan_type,
            "valid_from": newest.valid_from.isoformat(),
            "valid_to": newest.valid_to.isoformat(),
            **describe(newest),
        }

    log_audit(
        session,
        "insurance.lookup",
        "InsurancePolicy",
        entity_id=result.get("policy_id"),
        details={"patient_id": patient_id, "status": result["status"]},
        actor_user_id=actor_user_id,
    )
    session.commit()
    return result


def check_eligibility(
    session: Session,
    appointment_id: int,
    actor_user_id: int | None = None,
) -> InsuranceEligibilityCheck:
    """Run an eligibility pre-check for an appointment against the patient's policy."""
    action = "insurance.eligibility_checked"
    try:
        appointment = session.get(Appointment, appointment_id)
        if appointment is None:
            raise AppointmentNotFoundError(f"No appointment with id {appointment_id}")

        patient = session.get(PatientProfile, appointment.patient_id)
        if patient is None:
            raise PatientNotFoundError(f"No patient profile with id {appointment.patient_id}")

        policy = get_active_policy(session, patient.id)
        visit_type = appointment.visit_type
        details: dict = {"visit_type": visit_type}

        if policy is None:
            status = "not_covered"
            reason = lookup_insurance(session, patient.id)
            summary = (
                f"We could not confirm insurance coverage for this visit. "
                f"{reason['reason']}. This is an eligibility estimate, not a payment guarantee."
            )
            details["reason"] = reason["status"]
        else:
            plan = policy.plan_type.lower()
            details["plan"] = policy.plan_type
            details["provider"] = policy.provider_name
            needs_pre_auth = plan in ("bronze",) or (
                plan in ("silver", "standard") and visit_type in ("procedure", "imaging")
            )
            if needs_pre_auth:
                status = "needs_pre_authorization"
                summary = (
                    f"Your {policy.provider_name} {policy.plan_type} plan may cover this {visit_type} visit, "
                    f"but a pre-authorization is required before it can be scheduled. "
                    f"Contact your insurer to request one. This is an eligibility estimate, not a payment guarantee."
                )
            else:
                status = "covered"
                summary = (
                    f"Your {policy.provider_name} {policy.plan_type} plan covers {visit_type} visits at "
                    f"{appointment.department.name}. This is an eligibility estimate, not a payment guarantee."
                )

        check = InsuranceEligibilityCheck(
            appointment_id=appointment.id,
            policy_id=policy.id if policy else None,
            status=status,
            coverage_summary=summary,
            details=details,
            checked_at=datetime.now(),
        )
        session.add(check)
        session.flush()
        log_audit(
            session,
            action,
            "InsuranceEligibilityCheck",
            entity_id=check.id,
            details={"appointment_id": appointment.id, "status": status, "policy_id": check.policy_id},
            actor_user_id=actor_user_id,
        )
        session.commit()
        session.refresh(check)
        return check
    except Exception as exc:
        session.rollback()
        log_audit(
            session,
            f"{action}.failed",
            "InsuranceEligibilityCheck",
            details={"appointment_id": appointment_id, "reason": str(exc)},
            actor_user_id=actor_user_id,
        )
        session.commit()
        raise