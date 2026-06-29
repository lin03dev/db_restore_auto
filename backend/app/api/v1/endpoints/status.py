from fastapi import APIRouter, Depends

from app.api.deps import get_orchestrator_service
from app.core.security import verify_api_key
from app.schemas import StatusResponse
from app.services.orchestrator import OrchestratorService

router = APIRouter()


@router.get("/status", response_model=StatusResponse)
def get_status(
    _: None = Depends(verify_api_key),
    service: OrchestratorService = Depends(get_orchestrator_service),
):
    return service.get_status()
