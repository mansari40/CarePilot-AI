class ToolError(Exception):
    """Base class for all tool errors."""


class PatientNotFoundError(ToolError):
    pass


class DepartmentNotFoundError(ToolError):
    pass


class DoctorNotFoundError(ToolError):
    pass


class SlotNotFoundError(ToolError):
    pass


class SlotUnavailableError(ToolError):
    pass


class AppointmentNotFoundError(ToolError):
    pass


class AppointmentNotActiveError(ToolError):
    pass


class DuplicateDocumentError(ToolError):
    pass


class ReminderValidationError(ToolError):
    pass


class EscalationNotOpenError(ToolError):
    pass


class WorkflowRunNotFoundError(ToolError):
    pass


class InsuranceLookupError(ToolError):
    pass


class BillingUnavailableError(ToolError):
    pass