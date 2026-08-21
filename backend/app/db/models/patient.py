from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    date_of_birth: Mapped[date] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(20))
    phone: Mapped[str | None] = mapped_column(String(30))
    preferred_language: Mapped[str] = mapped_column(String(10), default="en")
    contact_status: Mapped[str] = mapped_column(
        String(20), default="new", index=True
    )
    emergency_contact_name: Mapped[str | None] = mapped_column(String(150))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="profile")
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan", passive_deletes=True
    )
    documents: Mapped[list["PatientDocument"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan", passive_deletes=True
    )
    workflows: Mapped[list["WorkflowRun"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan", passive_deletes=True
    )
    policies: Mapped[list["InsurancePolicy"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan", passive_deletes=True
    )