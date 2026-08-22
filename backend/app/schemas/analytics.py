"""Analytics response schemas."""

from pydantic import BaseModel


class DepartmentCount(BaseModel):
    department: str
    count: int


class StatusCount(BaseModel):
    status: str
    count: int


class AvgBooking(BaseModel):
    average_seconds: float
    sample_count: int


class DocumentCompletion(BaseModel):
    total_appointments: int
    appointments_with_documents: int
    completion_rate_pct: float
    total_documents: int
    duplicate_documents: int
    duplicate_rate_pct: float


class SeverityCount(BaseModel):
    severity: str
    count: int


class EscalationStats(BaseModel):
    total: int
    open: int
    resolved: int
    avg_resolution_seconds: float
    by_severity: list[SeverityCount]


class DoctorLoad(BaseModel):
    doctor: str
    department: str
    appointment_count: int


class DayCount(BaseModel):
    day: str | None
    count: int


class DashboardResponse(BaseModel):
    appointments_by_department: list[DepartmentCount]
    appointments_by_status: list[StatusCount]
    avg_request_to_booking: AvgBooking
    document_completion: DocumentCompletion
    escalation_stats: EscalationStats
    insurance_eligibility_outcomes: list[StatusCount]
    busiest_doctors: list[DoctorLoad]
    busiest_days: list[DayCount]
