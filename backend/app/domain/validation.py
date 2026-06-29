import subprocess
from typing import List, Optional, Tuple

import yaml

from app.core.config import Settings, get_settings
from app.domain.local_postgres import build_pg_env, resolve_local_db_config
from app.domain.selection import matches_database_targets
from app.infrastructure.postgres_tools import pg_tool_or_raise


def _load_config(settings: Settings) -> dict:
    with open(settings.databases_config) as handle:
        return yaml.safe_load(handle) or {}


def _local_db_config(settings: Optional[Settings] = None) -> dict:
    settings = settings or get_settings()
    return resolve_local_db_config(settings, _load_config(settings))


def _configured_databases(
    target_names: Optional[List[str]] = None,
    settings: Optional[Settings] = None,
) -> List[dict]:
    settings = settings or get_settings()
    config = _load_config(settings)
    return [
        db
        for db in config.get("databases", [])
        if db.get("enabled", True) and matches_database_targets(db, target_names)
    ]


def _target_db_names(
    target_names: Optional[List[str]] = None,
    settings: Optional[Settings] = None,
) -> List[str]:
    return [db["target_db"] for db in _configured_databases(target_names, settings)]


def _run_psql(database: str, query: str, settings: Optional[Settings] = None) -> subprocess.CompletedProcess:
    settings = settings or get_settings()
    psql = pg_tool_or_raise("psql")
    db_config = _local_db_config(settings)
    return subprocess.run(
        [
            psql,
            "-h",
            db_config["host"],
            "-p",
            str(db_config["port"]),
            "-U",
            db_config["username"],
            "-d",
            database,
            "-tAc",
            query,
        ],
        capture_output=True,
        text=True,
        env=build_pg_env(db_config),
    )


def quick_validate_database(database: str, settings: Optional[Settings] = None) -> bool:
    settings = settings or get_settings()
    print(f"\nQuick check for {database}:")
    print("-" * 40)

    try:
        pg_tool_or_raise("psql")
    except FileNotFoundError as exc:
        print(f"  ERROR: {exc}")
        return False

    result = _run_psql(
        database,
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema NOT IN ('information_schema', 'pg_catalog');",
        settings,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        if "password authentication failed" in detail.lower():
            print("  Failed to connect: local PostgreSQL authentication failed.")
            print("  Set LOCAL_DB_PASSWORD in backend/.env or local_postgres.password in databases.yaml.")
        else:
            print("  Failed to connect.")
        return False

    print(f"  Tables: {result.stdout.strip()}")
    return True


def full_validate_database(
    database: str,
    settings: Optional[Settings] = None,
) -> Tuple[bool, int]:
    settings = settings or get_settings()
    try:
        pg_tool_or_raise("psql")
    except FileNotFoundError:
        return False, 0

    result = _run_psql(
        database,
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';",
        settings,
    )
    if result.returncode == 0 and result.stdout.strip():
        count = int(result.stdout.strip())
        return count > 0, count
    return False, 0


def run_quick_validation(
    target_names: Optional[List[str]] = None,
    settings: Optional[Settings] = None,
) -> bool:
    settings = settings or get_settings()
    targets = _target_db_names(target_names, settings)
    print("\n" + "=" * 60)
    print("QUICK POST-RESTORE VALIDATION")
    print("=" * 60)
    if target_names:
        print(f"  Selected: {', '.join(target_names)}")

    if not targets:
        print("No databases selected for validation.")
        return False

    all_healthy = all(quick_validate_database(db, settings) for db in targets)

    print("\n" + "=" * 60)
    print(
        "All databases passed quick validation."
        if all_healthy
        else "Some databases have issues."
    )
    print("=" * 60)
    return all_healthy


def run_full_validation(
    target_names: Optional[List[str]] = None,
    settings: Optional[Settings] = None,
) -> bool:
    settings = settings or get_settings()
    targets = _target_db_names(target_names, settings)
    print("\n" + "=" * 60)
    print("VALIDATION RESULTS")
    print("=" * 60)
    if target_names:
        print(f"  Selected: {', '.join(target_names)}")

    if not targets:
        print("No databases selected for validation.")
        return False

    all_valid = True
    for db in targets:
        success, tables = full_validate_database(db, settings)
        if success:
            print(f"\n  {db}: {tables} tables")
        else:
            print(f"\n  {db}: No tables found")
            all_valid = False

    print("\n" + "=" * 60)
    print(
        "All databases validated successfully."
        if all_valid
        else "Validation failed - some databases have no data."
    )
    return all_valid
