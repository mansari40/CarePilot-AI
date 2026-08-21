from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), index=True
    )
    doctor_id: Mapped[int | None] = mapped_column(
        ForeignKey("doctors.id", ondelete="RESTRICT"), index=True
    )
    slot_id: Mapped[int | None] = mapped_column(
        ForeignKey("appointment_slots.id", ondelete="SET NULL"), unique=True
    )
    status: Mapped[str] = mapped_column(String(30), default="requested", index=True)
    visit_type: Mapped[str] = mapped_column(String(50), default="consultation")
    reason: Mapped[str | None] = mapped_column(Text)
    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    patient: Mapped["PatientProfile"] = relationship(back_populates="appointments")
    department: Mapped["Department"] = relationship()
    doctor: Mapped["Doctor | None"] = relationship()
    slot: Mapped["AppointmentSlot | None"] = relationship()
    documents: Mapped[list["PatientDocument"]] = relationship(
        back_populates="appointment", cascade="all, delete-orphan", passive_deletes=True
    )
    reminders: Mapped[list["Reminder"]] = relationship(
        back_populates="appointment", cascade="all, delete-orphan", passive_deletes=True
    )
    eligibility_checks: Mapped[list["InsuranceEligibilityCheck"]] = relationship(
        back_populates="appointment", cascade="all, delete-orphan", passive_deletes=True
    )
    billing_line_items: Mapped[list["BillingLineItem"]] = relationship(
        back_populates="appointment", cascade="all, delete-orphan", passive_deletes=True
    )
    billing_explanations: Mapped[list["BillingExplanation"]] = relationship(
        back_populates="appointment", cascade="all, delete-orphan", passive_deletes=True
    )