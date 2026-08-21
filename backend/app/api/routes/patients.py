"""Patient routes — profile and own records."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_patient_profile, get_current_user, get_db
from app.db.models import PatientProfile, User
from app.schemas.user import PatientProfileRead, PatientProfileUpdate, UserRead

router = APIRouter(prefix="/api/patients", tags=["patients"])


@router.get("/me", response_model=PatientProfileRead)
def read_own_profile(
    current_user: Annotated[User, Depends(get_current_user)],
    profile: Annotated[PatientProfile, Depends(get_current_patient_profile)],
) -> PatientProfileRead:
    return PatientProfileRead.model_validate(profile)


@router.patch("/me", response_model=PatientProfileRead)
def update_own_profile(
    payload: PatientProfileUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    profile: Annotated[PatientProfile, Depends(get_current_patient_profile)],
    db: Annotated[Session, Depends(get_db)],
) -> PatientProfileRead:
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return PatientProfileRead.model_validate(profile)
