from pathlib import Path
from typing import Any, List, Optional

import yaml
from app.core.errors import ConfigurationError, UnknownDatabaseError
from app.core.config import Settings, get_settings
from app.schemas import DatabaseConfig


class DatabaseConfigService:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    def load_raw(self) -> dict[str, Any]:
        config_path = self.settings.databases_config
        if not config_path.exists():
            raise ConfigurationError(
                f"Database configuration file is missing: {config_path}"
            )
        with open(config_path) as handle:
            data = yaml.safe_load(handle) or {}
        if "databases" not in data:
            raise ConfigurationError("databases.yaml must contain a 'databases' list")
        return data

    def list_databases(self) -> list[DatabaseConfig]:
        config = self.load_raw()
        return [
            DatabaseConfig(
                name=db["name"],
                target_db=db["target_db"],
                source_dump=db["source_dump"],
                enabled=db.get("enabled", True),
                description=db.get("description"),
            )
            for db in config.get("databases", [])
        ]

    def allowed_database_names(self) -> set[str]:
        allowed: set[str] = set()
        for db in self.list_databases():
            allowed.add(db.name.lower())
            allowed.add(db.target_db.lower())
        return allowed

    def resolve_canonical_names(self, selections: List[str]) -> List[str]:
        """Map user selections (name or target_db) to configured database names."""
        if not selections:
            return [db.name for db in self.list_databases() if db.enabled]

        config = self.load_raw()
        resolved: list[str] = []
        for selection in selections:
            key = selection.lower()
            matched = None
            for db in config.get("databases", []):
                if db["name"].lower() == key or db.get("target_db", "").lower() == key:
                    matched = db["name"]
                    break
            if not matched:
                raise UnknownDatabaseError(f"Unknown database: {selection}")
            if matched not in resolved:
                resolved.append(matched)
        return resolved

    def validate_database_targets(self, databases: List[str]) -> List[str]:
        if not databases:
            return self.resolve_canonical_names([])
        return self.resolve_canonical_names(databases)

    def validate_database_target(self, database: str) -> str:
        if database.lower() == "both":
            return "both"
        names = self.resolve_canonical_names([database])
        return names[0] if names else database

    @staticmethod
    def dump_filename(dump_path: str) -> str:
        return Path(dump_path).name
