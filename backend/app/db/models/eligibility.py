from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class InsuranceEligibilityCheck(Base):
    __tablename__ = "insurance_eligibility_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    appointment_id: Mapped[int] = mapped_column(
        ForeignKey("appointments.id", ondelete="CASCADE"), index=True
    )
    policy_id: Mapped[int | None] = mapped_column(
        ForeignKey("insurance_policies.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    coverage_summary: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSONB)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    appointment: Mapped["Appointment"] = relationship(back_populates="eligibility_checks")
    policy: Mapped["InsurancePolicy | None"] = relationship(
        back_populates="eligibility_checks"
    )