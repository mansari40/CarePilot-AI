from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=20)
    description: str | None = Field(default=None, max_length=500)
    building: str | None = Field(default=None, max_length=100)
    floor: str | None = Field(default=None, max_length=20)
    is_active: bool = True


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    building: str | None = Field(default=None, max_length=100)
    floor: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None


class DepartmentRead(BaseModel):
    id: int
    name: str
    code: str
    description: str | None
    building: str | None
    floor: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class DoctorCreate(BaseModel):
    department_id: int
    name: str = Field(min_length=1, max_length=150)
    specialty: str = Field(min_length=1, max_length=150)
    license_number: str = Field(min_length=1, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    is_active: bool = True


class DoctorUpdate(BaseModel):
    department_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=150)
    specialty: str | None = Field(default=None, min_length=1, max_length=150)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    is_active: bool | None = None


class DoctorRead(BaseModel):
    id: int
    department_id: int
    name: str
    specialty: str
    license_number: str
    email: str | None
    phone: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class AppointmentSlotCreate(BaseModel):
    doctor_id: int
    start_time: datetime
    end_time: datetime


class AppointmentSlotRead(BaseModel):
    id: int
    doctor_id: int
    start_time: datetime
    end_time: datetime
    is_booked: bool

    model_config = ConfigDict(from_attributes=True)