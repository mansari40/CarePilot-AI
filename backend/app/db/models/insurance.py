from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class InsurancePolicy(Base):
    __tablename__ = "insurance_policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient_profiles.id", ondelete="CASCADE"), index=True
    )
    provider_name: Mapped[str] = mapped_column(String(150))
    policy_number: Mapped[str] = mapped_column(String(100), unique=True)
    plan_type: Mapped[str] = mapped_column(String(50), default="standard")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    patient: Mapped["PatientProfile"] = relationship(back_populates="policies")
    eligibility_checks: Mapped[list["InsuranceEligibilityCheck"]] = relationship(
        back_populates="policy", cascade="all, delete-orphan", passive_deletes=True
    )