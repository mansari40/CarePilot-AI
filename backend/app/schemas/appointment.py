from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AppointmentStatus = Literal[
    "requested", "scheduled", "confirmed", "completed", "cancelled", "rescheduled"
]


class AppointmentCreate(BaseModel):
    patient_id: int
    department_id: int
    doctor_id: int | None = None
    slot_id: int | None = None
    visit_type: str = "consultation"
    reason: str | None = Field(default=None, max_length=2000)
    scheduled_for: datetime | None = None
    notes: str | None = None


class AppointmentUpdate(BaseModel):
    doctor_id: int | None = None
    slot_id: int | None = None
    status: AppointmentStatus | None = None
    visit_type: str | None = None
    reason: str | None = None
    scheduled_for: datetime | None = None
    notes: str | None = None


class AppointmentRead(BaseModel):
    id: int
    patient_id: int
    department_id: int
    doctor_id: int | None
    slot_id: int | None
    status: str
    visit_type: str
    reason: str | None
    scheduled_for: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)