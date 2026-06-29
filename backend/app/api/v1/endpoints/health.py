from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check():
    settings = get_settings()
    return HealthResponse(
        status="ok",
        environment=settings.environment,
        auth_enabled=settings.auth_enabled,
        version=settings.app_version,
    )
