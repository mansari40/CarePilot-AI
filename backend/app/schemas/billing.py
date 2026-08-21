from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class FeeScheduleItemCreate(BaseModel):
    department_id: int
    service_code: str = Field(min_length=1, max_length=50)
    description: str = Field(min_length=1, max_length=200)
    amount_usd: Decimal = Field(gt=0, decimal_places=2)
    category: str = Field(min_length=1, max_length=50)
    is_active: bool = True


class FeeScheduleItemRead(BaseModel):
    id: int
    department_id: int
    service_code: str
    description: str
    amount_usd: Decimal
    category: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class BillingLineItemRead(BaseModel):
    id: int
    appointment_id: int
    description: str
    amount_usd: Decimal
    category: str
    source: str | None

    model_config = ConfigDict(from_attributes=True)


class BillingExplanationRead(BaseModel):
    id: int
    appointment_id: int
    summary_text: str
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)