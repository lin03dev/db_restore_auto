from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class OperationType(str, Enum):
    pipeline = "pipeline"
    backup = "backup"
    restore = "restore"
    validate = "validate"


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class JobRequest(BaseModel):
    operation: OperationType = OperationType.pipeline
    databases: List[str] = Field(
        default_factory=list,
        description="Database names to include. Empty = all enabled databases.",
    )
    database: Optional[str] = Field(
        default=None,
        description="Deprecated single-database selector. Use databases instead.",
    )
    force_backup: bool = False
    force_restore: bool = False
    skip_backup: bool = False
    skip_restore: bool = False
    skip_validation: bool = False
    full_validation: bool = False

    @field_validator("databases", mode="before")
    @classmethod
    def normalize_databases(cls, value: Optional[List[str]]) -> List[str]:
        if not value:
            return []
        return [item.strip() for item in value if item and item.strip()]

    @model_validator(mode="after")
    def merge_legacy_database_field(self) -> "JobRequest":
        if self.database and self.database.strip().lower() != "both" and not self.databases:
            self.databases = [self.database.strip()]
        return self

    def selected_databases(self) -> List[str]:
        return self.databases

    def selection_label(self) -> str:
        if not self.databases:
            return "all"
        return ", ".join(self.databases)


class BackupInfo(BaseModel):
    name: str
    dump_file: str
    exists: bool
    size_mb: float
    age_days: Optional[int]
    needs_refresh: bool
    status: str


class RestoreInfo(BaseModel):
    target_db: str
    source_name: str
    last_restore: Optional[str]
    days_ago: Optional[int]
    can_restore: bool
    status: str


class StatusResponse(BaseModel):
    backups: list[BackupInfo]
    restores: list[RestoreInfo]


class JobResponse(BaseModel):
    id: str
    operation: OperationType
    status: JobStatus
    databases: List[str] = Field(default_factory=list)
    database: str = "all"
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    logs: list[str] = Field(default_factory=list)
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class DatabaseConfig(BaseModel):
    name: str
    target_db: str
    source_dump: str
    enabled: bool
    description: Optional[str] = None


class MessageResponse(BaseModel):
    success: bool
    message: str


class HealthResponse(BaseModel):
    status: str
    environment: str
    auth_enabled: bool
    version: str


class ConnectivityCheckRequest(BaseModel):
    databases: List[str] = Field(
        default_factory=list,
        description="Database names to test. Empty = all enabled databases.",
    )


class DatabaseConnectivityResult(BaseModel):
    name: str
    reachable: bool
    error_code: Optional[str] = None
    message: Optional[str] = None


class LocalPostgresStatus(BaseModel):
    reachable: bool
    host: str
    port: str
    username: str
    error_code: Optional[str] = None
    message: Optional[str] = None
