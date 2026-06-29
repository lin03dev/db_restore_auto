from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_job_service, get_orchestrator_service
from app.core.security import verify_api_key
from app.schemas import JobRequest, JobResponse, JobStatus, MessageResponse
from app.services.job_service import Job, JobService
from app.services.orchestrator import OrchestratorService

router = APIRouter()


def _job_to_response(job: Job) -> JobResponse:
    targets = job.request.selected_databases()
    return JobResponse(
        id=job.id,
        operation=job.operation,
        status=job.status,
        databases=targets,
        database=job.request.selection_label(),
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        logs=job.logs,
        result=job.result,
        error=job.error,
    )


@router.get("/jobs", response_model=list[JobResponse])
def list_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    _: None = Depends(verify_api_key),
    job_service: JobService = Depends(get_job_service),
):
    return [_job_to_response(job) for job in job_service.list_jobs(limit)]


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    _: None = Depends(verify_api_key),
    job_service: JobService = Depends(get_job_service),
):
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return _job_to_response(job)


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def start_job(
    payload: JobRequest,
    _: None = Depends(verify_api_key),
    job_service: JobService = Depends(get_job_service),
    orchestrator: OrchestratorService = Depends(get_orchestrator_service),
):
    orchestrator.config_service.validate_database_targets(payload.selected_databases())
    try:
        job = job_service.create_job(payload)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return _job_to_response(job)


@router.post("/reset-tracking", response_model=MessageResponse)
def reset_tracking(
    _: None = Depends(verify_api_key),
    service: OrchestratorService = Depends(get_orchestrator_service),
):
    result = service.reset_tracking()
    return MessageResponse(success=result["success"], message=result["message"])
