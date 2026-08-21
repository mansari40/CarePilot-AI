from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EscalationCreate(BaseModel):
    workflow_run_id: int | None = None
    patient_id: int | None = None
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    reason: str = Field(min_length=1, max_length=200)
    details: str | None = None


class EscalationResolve(BaseModel):
    resolution_notes: str = Field(min_length=1)


class EscalationRead(BaseModel):
    id: int
    workflow_run_id: int | None
    patient_id: int | None
    severity: str
    reason: str
    details: str | None
    status: str
    resolved_at: datetime | None
    reviewed_by: int | None
    resolution_notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditEventRead(BaseModel):
    id: int
    actor_user_id: int | None
    action: str
    entity_type: str
    entity_id: int | None
    details: dict | None
    ip_address: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)