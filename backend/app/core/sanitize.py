import re
from typing import Pattern

SENSITIVE_PATTERNS: list[Pattern[str]] = [
    re.compile(r"postgresql://\S+", re.IGNORECASE),
    re.compile(r"password[=:]\S+", re.IGNORECASE),
    re.compile(r"PGPASSWORD=\S+", re.IGNORECASE),
]


def sanitize_log_line(line: str) -> str:
    sanitized = line
    for pattern in SENSITIVE_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)
    return sanitized
