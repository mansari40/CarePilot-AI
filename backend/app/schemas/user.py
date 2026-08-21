from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=150)
    role: Literal["patient", "staff"] = "patient"


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRead(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PatientProfileCreate(BaseModel):
    date_of_birth: date
    gender: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=30)
    preferred_language: str = "en"
    contact_status: Literal["new", "contacted", "active"] = "new"
    emergency_contact_name: str | None = Field(default=None, max_length=150)
    emergency_contact_phone: str | None = Field(default=None, max_length=30)


class PatientProfileUpdate(BaseModel):
    phone: str | None = Field(default=None, max_length=30)
    preferred_language: str | None = Field(default=None, max_length=10)
    contact_status: Literal["new", "contacted", "active"] | None = None
    emergency_contact_name: str | None = Field(default=None, max_length=150)
    emergency_contact_phone: str | None = Field(default=None, max_length=30)


class PatientProfileRead(BaseModel):
    id: int
    user_id: int
    date_of_birth: date
    gender: str | None
    phone: str | None
    preferred_language: str
    contact_status: str
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)