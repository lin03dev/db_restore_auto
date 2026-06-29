import io
import threading
import uuid
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from typing import Any, Optional

from app.core.config import get_settings
from app.core.sanitize import sanitize_log_line
from app.schemas import JobRequest, JobStatus, OperationType
from app.services.orchestrator import OrchestratorService


class _LogCapture(io.StringIO):
    def __init__(self, logs: list[str]):
        super().__init__()
        self._logs = logs
        self._buffer = ""

    def write(self, text: str) -> int:
        if not text:
            return 0
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line.strip():
                self._logs.append(sanitize_log_line(line))
        return len(text)

    def flush(self) -> None:
        if self._buffer.strip():
            self._logs.append(sanitize_log_line(self._buffer.strip()))
            self._buffer = ""


class Job:
    def __init__(self, request: JobRequest):
        self.id = str(uuid.uuid4())
        self.request = request
        self.operation = request.operation
        self.status = JobStatus.pending
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.finished_at: Optional[datetime] = None
        self.logs: list[str] = []
        self.result: Optional[dict[str, Any]] = None
        self.error: Optional[str] = None


class JobService:
    def __init__(self, max_jobs: int = 50):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._max_jobs = max_jobs

    def create_job(self, request: JobRequest) -> Job:
        with self._lock:
            if any(
                job.status in (JobStatus.pending, JobStatus.running)
                for job in self._jobs.values()
            ):
                raise RuntimeError("A job is already running")

            job = Job(request)
            self._jobs[job.id] = job
            if len(self._jobs) > self._max_jobs:
                oldest = sorted(self._jobs.values(), key=lambda item: item.created_at)
                for old in oldest[: len(self._jobs) - self._max_jobs]:
                    del self._jobs[old.id]

        thread = threading.Thread(target=self._run_job, args=(job,), daemon=True)
        thread.start()
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list_jobs(self, limit: int = 20) -> list[Job]:
        jobs = sorted(self._jobs.values(), key=lambda item: item.created_at, reverse=True)
        return jobs[:limit]

    def _run_job(self, job: Job) -> None:
        job.status = JobStatus.running
        job.started_at = datetime.now()
        capture = _LogCapture(job.logs)

        try:
            service = OrchestratorService()
            with redirect_stdout(capture), redirect_stderr(capture):
                job.result = service.execute(job.request)
            success = bool(job.result.get("success")) if job.result else False
            job.status = JobStatus.completed if success else JobStatus.failed
        except Exception as exc:
            job.error = sanitize_log_line(str(exc))
            job.logs.append(f"ERROR: {job.error}")
            job.status = JobStatus.failed
        finally:
            capture.flush()
            job.finished_at = datetime.now()


job_service = JobService(max_jobs=get_settings().max_jobs)
