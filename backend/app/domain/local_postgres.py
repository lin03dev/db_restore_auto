import os
import subprocess
from typing import Any, Dict, Optional, Tuple

from app.core.config import Settings, get_settings
from app.domain.connectivity import classify_connection_error
from app.infrastructure.postgres_tools import find_pg_tool

LOCAL_CONNECTION_TIMEOUT_SECONDS = 15

ENV_PASSWORD_PLACEHOLDERS = frozenset(
    {
        "",
        "your_local_password",
        "change-me",
        "changeme",
    }
)


def _effective_password(env_password: str, yaml_password: str) -> str:
    if env_password and env_password not in ENV_PASSWORD_PLACEHOLDERS:
        return env_password
    return yaml_password


def resolve_local_db_config(
    settings: Optional[Settings] = None,
    yaml_config: Optional[dict[str, Any]] = None,
) -> Dict[str, str]:
    """Merge .env local DB settings with optional databases.yaml local_postgres."""
    settings = settings or get_settings()
    yaml_local = (yaml_config or {}).get("local_postgres") or {}

    if hasattr(settings, "local_db_config"):
        env_local = settings.local_db_config
        host = env_local.get("host", "localhost")
        port = str(env_local.get("port", 5432))
        username = env_local.get("username", "postgres")
        password = env_local.get("password", "")
    else:
        host = getattr(settings, "local_db_host", "localhost")
        port = str(getattr(settings, "local_db_port", 5432))
        username = getattr(settings, "local_db_user", "postgres")
        password = getattr(settings, "local_db_password", "") or ""

    yaml_password = str(yaml_local.get("password") or "")
    password = _effective_password(password, yaml_password)

    return {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
    }


def build_pg_env(local: Dict[str, str]) -> Dict[str, str]:
    """Build subprocess env for local PostgreSQL tools.

    Only set PGPASSWORD when a password is configured — do not wipe an
    existing shell PGPASSWORD with an empty string.
    """
    env = os.environ.copy()
    password = local.get("password") or ""
    if password:
        env["PGPASSWORD"] = password
    return env


def test_local_connection(
    local: Dict[str, str],
    timeout_seconds: int = LOCAL_CONNECTION_TIMEOUT_SECONDS,
) -> Tuple[bool, str, str]:
    """Return (ok, error_code, message) for the local restore target."""
    try:
        psql_path = find_pg_tool("psql")
        if not psql_path:
            return False, "tool_missing", "psql was not found on PATH"

        if not local.get("password") and not os.environ.get("PGPASSWORD"):
            return (
                False,
                "missing_credentials",
                "Local PostgreSQL password is not set. "
                "Set LOCAL_DB_PASSWORD in backend/.env or local_postgres.password in config/databases.yaml.",
            )

        result = subprocess.run(
            [
                psql_path,
                "-h",
                local["host"],
                "-p",
                str(local["port"]),
                "-U",
                local["username"],
                "-d",
                "postgres",
                "-tAc",
                "SELECT 1",
            ],
            capture_output=True,
            text=True,
            env=build_pg_env(local),
            timeout=timeout_seconds,
        )
        if result.returncode == 0 and result.stdout.strip() == "1":
            return True, "", ""

        code, message = classify_connection_error(result.stderr, result.stdout)
        if code == "auth_failed":
            message = (
                "Local PostgreSQL authentication failed. "
                "Check LOCAL_DB_PASSWORD in backend/.env or local_postgres in config/databases.yaml."
            )
        return False, code, message
    except subprocess.TimeoutExpired:
        return False, "unreachable", "Timed out connecting to local PostgreSQL."
    except Exception as exc:
        return False, "connection_error", str(exc)[:300]
