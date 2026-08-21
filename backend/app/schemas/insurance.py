from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InsurancePolicyCreate(BaseModel):
    patient_id: int
    provider_name: str = Field(min_length=1, max_length=150)
    policy_number: str = Field(min_length=1, max_length=100)
    plan_type: str = Field(default="standard", max_length=50)
    active: bool = True
    valid_from: date
    valid_to: date


class InsurancePolicyRead(BaseModel):
    id: int
    patient_id: int
    provider_name: str
    policy_number: str
    plan_type: str
    active: bool
    valid_from: date
    valid_to: date
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InsuranceEligibilityCheckRead(BaseModel):
    id: int
    appointment_id: int
    policy_id: int | None
    status: Literal["pending", "covered", "not_covered", "needs_pre_authorization", "unknown"]
    coverage_summary: str | None
    details: dict | None
    checked_at: datetime

    model_config = ConfigDict(from_attributes=True)