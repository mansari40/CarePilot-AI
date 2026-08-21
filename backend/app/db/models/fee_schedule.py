from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class FeeScheduleItem(Base):
    __tablename__ = "fee_schedule_items"
    __table_args__ = (
        UniqueConstraint("department_id", "service_code", name="uq_fee_department_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), index=True
    )
    service_code: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(String(200))
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    category: Mapped[str] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    department: Mapped["Department"] = relationship()