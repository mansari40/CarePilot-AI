"""Staff routes — departments, doctors, slots CRUD (staff-only)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_staff
from app.db.models import Department, Doctor, AppointmentSlot, User
from app.schemas.admin import (
    AppointmentSlotCreate,
    AppointmentSlotRead,
    DepartmentCreate,
    DepartmentRead,
    DepartmentUpdate,
    DoctorCreate,
    DoctorRead,
    DoctorUpdate,
)

router = APIRouter(prefix="/api/staff", tags=["staff"])


# ── Departments ──────────────────────────────────────────────────────────────

@router.get("/departments", response_model=list[DepartmentRead])
def list_departments(
    staff: Annotated[User, Depends(require_staff)],
    db: Annotated[Session, Depends(get_db)],
) -> list[DepartmentRead]:
    depts = db.query(Department).order_by(Department.name).all()
    return [DepartmentRead.model_validate(d) for d in depts]


@router.post("/departments", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentCreate,
    staff: Annotated[User, Depends(require_staff)],
    db: Annotated[Session, Depends(get_db)],
) -> DepartmentRead:
    existing = db.query(Department).filter(Department.name == payload.name).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Department name already exists")
    dept = Department(**payload.model_dump())
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return DepartmentRead.model_validate(dept)


@router.get("/departments/{dept_id}", response_model=DepartmentRead)
def read_department(
    dept_id: int,
    staff: Annotated[User, Depends(require_staff)],
    db: Annotated[Session, Depends(get_db)],
) -> DepartmentRead:
    dept = db.get(Department, dept_id)
    if dept is None:
        raise HTTPException(status_code=404, detail="Department not found")
    return DepartmentRead.model_validate(dept)


@router.patch("/departments/{dept_id}", response_model=DepartmentRead)
def update_department(
    dept_id: int,
    payload: DepartmentUpdate,
    staff: Annotated[User, Depends(require_staff)],
    db: Annotated[Session, Depends(get_db)],
) -> DepartmentRead:
    dept = db.get(Department, dept_id)
    if dept is None:
        raise HTTPException(status_code=404, detail="Department not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(dept, field, value)
    db.commit()
    db.refresh(dept)
    return DepartmentRead.model_validate(dept)


# ── Doctors ──────────────────────────────────────────────────────────────────

@router.get("/doctors", response_model=list[DoctorRead])
def list_doctors(
    staff: Annotated[User, Depends(require_staff)],
    db: Annotated[Session, Depends(get_db)],
) -> list[DoctorRead]:
    doctors = db.query(Doctor).order_by(Doctor.name).all()
    return [DoctorRead.model_validate(d) for d in doctors]


@router.post("/doctors", response_model=DoctorRead, status_code=status.HTTP_201_CREATED)
def create_doctor(
    payload: DoctorCreate,
    staff: Annotated[User, Depends(require_staff)],
    db: Annotated[Session, Depends(get_db)],
) -> DoctorRead:
    if db.get(Department, payload.department_id) is None:
        raise HTTPException(status_code=404, detail="Department not found")
    existing = db.query(Doctor).filter(Doctor.license_number == payload.license_number).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="License number already exists")
    doctor = Doctor(**payload.model_dump())
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return DoctorRead.model_validate(doctor)


@router.get("/doctors/{doctor_id}", response_model=DoctorRead)
def read_doctor(
    doctor_id: int,
    staff: Annotated[User, Depends(require_staff)],
    db: Annotated[Session, Depends(get_db)],
) -> DoctorRead:
    doctor = db.get(Doctor, doctor_id)
    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return DoctorRead.model_validate(doctor)


@router.patch("/doctors/{doctor_id}", response_model=DoctorRead)
def update_doctor(
    doctor_id: int,
    payload: DoctorUpdate,
    staff: Annotated[User, Depends(require_staff)],
    db: Annotated[Session, Depends(get_db)],
) -> DoctorRead:
    doctor = db.get(Doctor, doctor_id)
    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(doctor, field, value)
    db.commit()
    db.refresh(doctor)
    return DoctorRead.model_validate(doctor)


# ── Slots ────────────────────────────────────────────────────────────────────

@router.get("/slots", response_model=list[AppointmentSlotRead])
def list_slots(
    staff: Annotated[User, Depends(require_staff)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AppointmentSlotRead]:
    slots = db.query(AppointmentSlot).order_by(AppointmentSlot.start_time).all()
    return [AppointmentSlotRead.model_validate(s) for s in slots]


@router.post("/slots", response_model=AppointmentSlotRead, status_code=status.HTTP_201_CREATED)
def create_slot(
    payload: AppointmentSlotCreate,
    staff: Annotated[User, Depends(require_staff)],
    db: Annotated[Session, Depends(get_db)],
) -> AppointmentSlotRead:
    if db.get(Doctor, payload.doctor_id) is None:
        raise HTTPException(status_code=404, detail="Doctor not found")
    slot = AppointmentSlot(**payload.model_dump())
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return AppointmentSlotRead.model_validate(slot)
