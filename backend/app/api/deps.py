from functools import lru_cache

from app.core.config import Settings, get_settings
from app.services.database_config import DatabaseConfigService
from app.services.job_service import JobService, job_service
from app.services.orchestrator import OrchestratorService


@lru_cache
def get_orchestrator_service() -> OrchestratorService:
    return OrchestratorService(get_settings())


@lru_cache
def get_database_config_service() -> DatabaseConfigService:
    return DatabaseConfigService(get_settings())


def get_job_service() -> JobService:
    return job_service


def get_settings_dep() -> Settings:
    return get_settings()
