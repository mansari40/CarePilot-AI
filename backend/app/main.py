from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.escalations import router as escalations_router
from app.api.routes.patients import router as patients_router
from app.api.routes.staff import router as staff_router
from app.api.workflows import router as workflows_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api")


@api.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


app.include_router(api)
app.include_router(auth_router)
app.include_router(patients_router)
app.include_router(workflows_router)
app.include_router(staff_router)
app.include_router(escalations_router)


@app.get("/health")
def root_health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
