from fastapi import APIRouter, Depends

from app.api.deps import get_orchestrator_service
from app.core.security import verify_api_key
from app.schemas import (
    ConnectivityCheckRequest,
    DatabaseConfig,
    DatabaseConnectivityResult,
    LocalPostgresStatus,
)
from app.services.orchestrator import OrchestratorService

router = APIRouter()


@router.get("/databases", response_model=list[DatabaseConfig])
def list_databases(
    _: None = Depends(verify_api_key),
    service: OrchestratorService = Depends(get_orchestrator_service),
):
    return service.get_databases()


@router.post("/databases/connectivity", response_model=list[DatabaseConnectivityResult])
def check_database_connectivity(
    payload: ConnectivityCheckRequest,
    _: None = Depends(verify_api_key),
    service: OrchestratorService = Depends(get_orchestrator_service),
):
    return service.check_connectivity(payload.databases)


@router.get("/databases/local-connectivity", response_model=LocalPostgresStatus)
def check_local_postgres_connectivity(
    _: None = Depends(verify_api_key),
    service: OrchestratorService = Depends(get_orchestrator_service),
):
    return service.check_local_postgres()
