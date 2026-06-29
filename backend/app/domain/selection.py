"""Shared helpers for filtering configured databases by user selection."""

from typing import Any, Dict, List, Optional


def matches_database_targets(db: Dict[str, Any], target_names: Optional[List[str]]) -> bool:
    """Return True if db should be processed (empty target_names = all)."""
    if not target_names:
        return True
    allowed = {name.lower() for name in target_names}
    return (
        db.get("name", "").lower() in allowed
        or db.get("target_db", "").lower() in allowed
    )
