"""Billing tool — fee-schedule lookups and plain-language billing explanations.

Line items are assembled from the real persisted fee schedule keyed by the
appointment's department; the explanation text is generated from those actual
line items. It is an explanation of expected costs, never a legally binding
invoice.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import (
    Appointment,
    BillingExplanation,
    BillingLineItem,
    FeeScheduleItem,
)
from app.tools.audit import log_audit
from app.tools.errors import AppointmentNotFoundError, BillingUnavailableError

_VISIT_TO_CATEGORY = {
    "consultation": "consultation",
    "checkup": "consultation",
    "new_patient": "consultation",
    "follow_up": "follow_up",
    "procedure": "procedure",
}


def lookup_fee_items(
    session: Session,
    department_id: int,
    category: str | None = None,
    actor_user_id: int | None = None,
) -> list[FeeScheduleItem]:
    query = session.query(FeeScheduleItem).filter(
        FeeScheduleItem.department_id == department_id,
        FeeScheduleItem.is_active.is_(True),
    )
    if category is not None:
        query = query.filter(FeeScheduleItem.category == category)
    items = query.order_by(FeeScheduleItem.category, FeeScheduleItem.service_code).all()
    log_audit(
        session,
        "billing.fee_schedule_lookup",
        "FeeScheduleItem",
        details={"department_id": department_id, "category": category, "count": len(items)},
        actor_user_id=actor_user_id,
    )
    session.commit()
    return items


def _fee_item_for(
    session: Session, department_id: int, category: str
) -> FeeScheduleItem | None:
    item = (
        session.query(FeeScheduleItem)
        .filter(
            FeeScheduleItem.department_id == department_id,
            FeeScheduleItem.category == category,
            FeeScheduleItem.is_active.is_(True),
        )
        .order_by(FeeScheduleItem.amount_usd)
        .first()
    )
    if item is None and category == "follow_up":
        item = (
            session.query(FeeScheduleItem)
            .filter(
                FeeScheduleItem.department_id == department_id,
                FeeScheduleItem.category == "consultation",
                FeeScheduleItem.is_active.is_(True),
            )
            .order_by(FeeScheduleItem.amount_usd)
            .first()
        )
    if item is None and category == "procedure":
        item = (
            session.query(FeeScheduleItem)
            .filter(
                FeeScheduleItem.department_id == department_id,
                FeeScheduleItem.category == "consultation",
                FeeScheduleItem.is_active.is_(True),
            )
            .order_by(FeeScheduleItem.amount_usd)
            .first()
        )
    return item


def _facility_fee(session: Session, department_id: int) -> FeeScheduleItem | None:
    return (
        session.query(FeeScheduleItem)
        .filter(
            FeeScheduleItem.department_id == department_id,
            FeeScheduleItem.service_code == "FACILITY",
            FeeScheduleItem.is_active.is_(True),
        )
        .first()
    )


def generate_billing_explanation(
    session: Session,
    appointment_id: int,
    actor_user_id: int | None = None,
) -> BillingExplanation:
    action = "billing.explanation_generated"
    try:
        appointment = session.get(Appointment, appointment_id)
        if appointment is None:
            raise AppointmentNotFoundError(f"No appointment with id {appointment_id}")

        category = _VISIT_TO_CATEGORY.get(appointment.visit_type, "consultation")
        base_item = _fee_item_for(session, appointment.department_id, category)
        if base_item is None:
            raise BillingUnavailableError(
                f"No fee schedule data for department {appointment.department_id} "
                f"(visit type '{appointment.visit_type}')"
            )

        line_items: list[BillingLineItem] = [
            BillingLineItem(
                appointment_id=appointment.id,
                description=base_item.description,
                amount_usd=base_item.amount_usd,
                category=base_item.category,
                source=f"fee_schedule:{base_item.service_code}",
            )
        ]
        facility = _facility_fee(session, appointment.department_id)
        if facility is not None:
            line_items.append(
                BillingLineItem(
                    appointment_id=appointment.id,
                    description=facility.description,
                    amount_usd=facility.amount_usd,
                    category=facility.category,
                    source=f"fee_schedule:{facility.service_code}",
                )
            )

        session.add_all(line_items)
        session.flush()

        total = sum(item.amount_usd for item in line_items)
        items_text = ", ".join(
            f"{item.description} (${item.amount_usd:.2f})" for item in line_items
        )
        summary_text = (
            f"This is an estimate of expected charges for your {appointment.visit_type.replace('_', ' ')} "
            f"appointment in {appointment.department.name}. Line items from our standard fee schedule: "
            f"{items_text}. Estimated total: ${total:.2f}. "
            f"Your insurance coverage may reduce what you pay. "
            f"This is an explanation of expected costs, not a legally binding invoice."
        )

        explanation = BillingExplanation(
            appointment_id=appointment.id, summary_text=summary_text
        )
        session.add(explanation)
        session.flush()
        log_audit(
            session,
            action,
            "BillingExplanation",
            entity_id=explanation.id,
            details={
                "appointment_id": appointment.id,
                "line_item_count": len(line_items),
                "estimated_total_usd": str(total),
            },
            actor_user_id=actor_user_id,
        )
        session.commit()
        session.refresh(explanation)
        return explanation
    except Exception as exc:
        session.rollback()
        log_audit(
            session,
            f"{action}.failed",
            "BillingExplanation",
            details={"appointment_id": appointment_id, "reason": str(exc)},
            actor_user_id=actor_user_id,
        )
        session.commit()
        raise