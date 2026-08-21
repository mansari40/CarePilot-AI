from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DocumentType = Literal[
    "ecg", "lab_report", "prescription", "referral", "id_proof", "imaging", "other"
]


class PatientDocumentCreate(BaseModel):
    patient_id: int
    appointment_id: int | None = None
    filename: str = Field(min_length=1, max_length=255)
    storage_path: str = Field(min_length=1, max_length=500)
    document_type: DocumentType = "other"
    checksum: str = Field(min_length=1, max_length=64)


class PatientDocumentRead(BaseModel):
    id: int
    patient_id: int
    appointment_id: int | None
    filename: str
    storage_path: str
    document_type: str
    checksum: str
    is_duplicate: bool
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)