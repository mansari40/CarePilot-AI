from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WorkflowRunCreate(BaseModel):
    patient_id: int
    request_text: str = Field(min_length=1)
    intent: str | None = Field(default=None, max_length=100)
    document_id: int | None = Field(
        default=None,
        description="Id of an already-uploaded patient document relevant to the request (e.g. an ECG).",
    )


class WorkflowResume(BaseModel):
    message: str = Field(min_length=1)
    document_id: int | None = Field(
        default=None,
        description="Id of an uploaded document supplied in response to an awaiting_document pause.",
    )


class WorkflowRunRead(BaseModel):
    id: int
    patient_id: int
    request_text: str
    intent: str | None
    status: str
    current_step: str | None
    thread_id: str | None
    summary: str | None
    state: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReminderCreate(BaseModel):
    appointment_id: int | None = None
    patient_id: int
    reminder_type: Literal["appointment", "follow_up"] = "appointment"
    scheduled_for: datetime
    channel: Literal["email", "sms", "in_app"] = "in_app"
    message: str | None = None


class ReminderRead(BaseModel):
    id: int
    appointment_id: int | None
    patient_id: int
    reminder_type: str
    scheduled_for: datetime
    sent_at: datetime | None
    channel: str
    message: str | None
    status: str
    appointment_date: datetime | None = None

    model_config = ConfigDict(from_attributes=True)