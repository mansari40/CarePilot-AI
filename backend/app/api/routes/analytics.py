"""Analytics routes -- staff-only dashboard."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_staff
from app.db.models import User
from app.schemas.analytics import DashboardResponse
from app.services.analytics_service import get_dashboard

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    staff: Annotated[User, Depends(require_staff)],
    db: Annotated[Session, Depends(get_db)],
) -> DashboardResponse:
    return DashboardResponse(**get_dashboard(db))
