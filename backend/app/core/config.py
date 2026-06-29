from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent

# Defaults aligned with frontend/vite.config.ts and backend/.env.example
DEFAULT_API_PORT = 8002
DEFAULT_FRONTEND_ORIGINS = (
    "http://localhost:5174",
    "http://127.0.0.1:5174",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = Field(default="DB Restore Automation", validation_alias="APP_NAME")
    app_version: str = Field(default="2.0.0", validation_alias="APP_VERSION")
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    debug: bool = True

    host: str = Field(default="127.0.0.1", validation_alias="HOST")
    port: int = Field(default=DEFAULT_API_PORT, validation_alias="PORT")
    reload: bool = Field(default=True, validation_alias="RELOAD")

    api_key: str = Field(default="", validation_alias="API_KEY")
    cors_origins: str = Field(
        default=",".join(DEFAULT_FRONTEND_ORIGINS),
        validation_alias="CORS_ORIGINS",
    )

    local_db_host: str = Field(default="localhost", validation_alias="LOCAL_DB_HOST")
    local_db_port: int = Field(default=5432, validation_alias="LOCAL_DB_PORT")
    local_db_user: str = Field(default="postgres", validation_alias="LOCAL_DB_USER")
    local_db_password: str = Field(default="", validation_alias="LOCAL_DB_PASSWORD")

    backup_max_age_days: int = Field(default=7, validation_alias="BACKUP_MAX_AGE_DAYS")
    restore_cooldown_days: int = Field(default=7, validation_alias="RESTORE_COOLDOWN_DAYS")
    backup_timeout_seconds: int = Field(default=7200, validation_alias="BACKUP_TIMEOUT_SECONDS")
    remote_connection_timeout_seconds: int = Field(
        default=20, validation_alias="REMOTE_CONNECTION_TIMEOUT_SECONDS"
    )
    local_connection_timeout_seconds: int = Field(
        default=15, validation_alias="LOCAL_CONNECTION_TIMEOUT_SECONDS"
    )
    max_jobs: int = Field(default=50, validation_alias="MAX_JOBS")

    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if self.is_production and not self.api_key:
            raise ValueError("API_KEY is required when ENVIRONMENT=production")
        return self

    @property
    def base_dir(self) -> Path:
        return BACKEND_ROOT

    @property
    def dumps_dir(self) -> Path:
        return BACKEND_ROOT / "dumps"

    @property
    def logs_dir(self) -> Path:
        return BACKEND_ROOT / "logs"

    @property
    def databases_config(self) -> Path:
        return BACKEND_ROOT / "config" / "databases.yaml"

    @property
    def local_db_config(self) -> dict:
        return {
            "host": self.local_db_host,
            "port": str(self.local_db_port),
            "username": self.local_db_user,
            "password": self.local_db_password,
        }

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_key)

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def ensure_directories(self) -> None:
        for path in (
            self.dumps_dir,
            self.logs_dir / "backup",
            self.logs_dir / "restore",
            self.logs_dir / "error",
            self.logs_dir / "reports",
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
