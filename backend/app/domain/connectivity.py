import re
import subprocess
from typing import Optional, Tuple

from app.infrastructure.postgres_tools import find_pg_tool

CONNECTION_TIMEOUT_SECONDS = 20

IP_RESTRICTION_PATTERNS = (
    "pg_hba.conf",
    "no pg_hba.conf entry",
    "not allowed to connect",
    "permission denied",
    "host is not allowed",
)

UNREACHABLE_PATTERNS = (
    "could not connect to server",
    "connection refused",
    "connection timed out",
    "timeout expired",
    "network is unreachable",
    "name or service not known",
    "temporary failure in name resolution",
    "server closed the connection unexpectedly",
)

AUTH_PATTERNS = (
    "password authentication failed",
    "authentication failed",
    "fe_sendauth",
)

DATABASE_IN_USE_PATTERNS = (
    "other sessions using the database",
    "is being accessed by other users",
    "database is being accessed",
)


def classify_connection_error(stderr: str, stdout: str = "") -> Tuple[str, str]:
    combined = f"{stderr}\n{stdout}".lower()

    if any(pattern in combined for pattern in IP_RESTRICTION_PATTERNS):
        return (
            "ip_restricted",
            "Remote connection blocked — your current IP may not be allowed. "
            "Connect via VPN or use an approved network, then retry.",
        )

    if any(pattern in combined for pattern in AUTH_PATTERNS):
        return (
            "auth_failed",
            "Authentication failed. Check the connection string credentials in your environment.",
        )

    if any(pattern in combined for pattern in DATABASE_IN_USE_PATTERNS):
        return (
            "database_in_use",
            "Database has open connections. Close apps using it, or retry — "
            "the restore process will terminate other sessions automatically.",
        )

    if any(pattern in combined for pattern in UNREACHABLE_PATTERNS):
        return (
            "unreachable",
            "Remote host is not reachable from this machine. Check VPN, firewall, or IP allowlisting.",
        )

    snippet = (stderr or stdout).strip().splitlines()
    message = snippet[-1] if snippet else "Unknown connection error"
    return "connection_error", message[:300]


def test_remote_connection(
    conn_string: str,
    pg_tool_path: Optional[str] = None,
    timeout_seconds: int = CONNECTION_TIMEOUT_SECONDS,
) -> Tuple[bool, str, str]:
    """Return (ok, error_code, message)."""
    try:
        psql_path = find_pg_tool(
            "psql",
            str(pg_tool_path).replace("pg_dump", "psql") if pg_tool_path else "psql",
        )
        if not psql_path and pg_tool_path:
            psql_path = find_pg_tool("psql")
        if not psql_path:
            return False, "tool_missing", "psql was not found on PATH"

        result = subprocess.run(
            [psql_path, conn_string, "-tAc", "SELECT 1"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        if result.returncode == 0 and result.stdout.strip() == "1":
            return True, "", ""

        code, message = classify_connection_error(result.stderr, result.stdout)
        return False, code, message
    except subprocess.TimeoutExpired:
        return (
            False,
            "unreachable",
            "Connection timed out — remote host may be blocked from this IP or network.",
        )
    except FileNotFoundError as exc:
        return False, "tool_missing", str(exc)
    except Exception as exc:
        return False, "connection_error", str(exc)[:300]


def is_non_retryable_error(error_code: str) -> bool:
    return error_code in {
        "ip_restricted",
        "unreachable",
        "auth_failed",
        "missing_credentials",
        "tool_missing",
    }
