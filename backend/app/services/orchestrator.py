from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from app.core.config import Settings, get_settings
from app.domain.backup import BackupManager
from app.domain.connectivity import test_remote_connection
from app.domain.local_postgres import resolve_local_db_config, test_local_connection
from app.domain.results import summarize_details
from app.domain.selection import matches_database_targets
from app.domain.restore import RestoreManager
from app.domain.validation import run_full_validation, run_quick_validation
from app.schemas import (
    BackupInfo,
    DatabaseConfig,
    JobRequest,
    OperationType,
    RestoreInfo,
    StatusResponse,
)
from app.services.database_config import DatabaseConfigService


class OrchestratorService:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.config_service = DatabaseConfigService(self.settings)

    def get_databases(self) -> list[DatabaseConfig]:
        return self.config_service.list_databases()

    def get_status(self) -> StatusResponse:
        backup_mgr = BackupManager(max_age_days=self.settings.backup_max_age_days)
        restore_mgr = RestoreManager(
            restore_cooldown_days=self.settings.restore_cooldown_days
        )

        backup_summary = backup_mgr.get_backup_summary()
        restore_status = restore_mgr.get_restore_status()
        config = self.config_service.load_raw()

        backups = []
        for db in config.get("databases", []):
            info = backup_summary.get(db["name"], {})
            age = info.get("age_days")
            if not info.get("exists"):
                db_status = "missing"
            elif info.get("needs_refresh"):
                db_status = "stale"
            else:
                db_status = "fresh"

            backups.append(
                BackupInfo(
                    name=db["name"],
                    dump_file=DatabaseConfigService.dump_filename(
                        info.get("dump_file", "")
                    ),
                    exists=info.get("exists", False),
                    size_mb=info.get("size_mb", 0),
                    age_days=age,
                    needs_refresh=info.get("needs_refresh", True),
                    status=db_status,
                )
            )

        restores = []
        for db in config.get("databases", []):
            target = db["target_db"]
            info = restore_status.get(target, {})
            can_restore = info.get("can_restore", True)
            days_ago = info.get("days_ago")

            if info.get("last_restore") is None:
                restore_status_label = "never"
            elif can_restore:
                restore_status_label = "ready"
            else:
                restore_status_label = "cooldown"

            restores.append(
                RestoreInfo(
                    target_db=target,
                    source_name=db["name"],
                    last_restore=info.get("last_restore"),
                    days_ago=days_ago,
                    can_restore=can_restore,
                    status=restore_status_label,
                )
            )

        return StatusResponse(backups=backups, restores=restores)

    def reset_tracking(self) -> dict[str, Any]:
        tracking_file = self.settings.base_dir / ".restore_tracking.json"
        if tracking_file.exists():
            tracking_file.unlink()
            return {"success": True, "message": "Restore tracking reset"}
        return {"success": True, "message": "No tracking file found"}

    def _resolve_targets(self, request: JobRequest) -> List[str]:
        return self.config_service.validate_database_targets(request.selected_databases())

    def _any_dump_available(self, targets: List[str]) -> bool:
        backup_mgr = BackupManager(max_age_days=self.settings.backup_max_age_days)
        available: list[str] = []
        for db in backup_mgr.config.get("databases", []):
            if not matches_database_targets(db, targets):
                continue
            dump_path = self.settings.dumps_dir / db["source_dump"]
            if dump_path.exists() and dump_path.stat().st_size > 0:
                available.append(f"{db['name']} ({dump_path.name}, {self.format_size(self.get_file_size_mb(dump_path))})")
        if available:
            print(f"\nLocal dumps available: {', '.join(available)}")
            return True
        print(
            f"\nNo non-empty dumps under {self.settings.dumps_dir}. "
            "If dumps exist on the host but not here, recreate the restore container "
            "(bind-mount backend/dumps) or run restore from the host CLI."
        )
        return False

    @staticmethod
    def format_size(size_mb: float) -> str:
        if size_mb < 1:
            return f"{size_mb * 1024:.1f} KB"
        if size_mb < 1024:
            return f"{size_mb:.1f} MB"
        return f"{size_mb / 1024:.2f} GB"

    @staticmethod
    def get_file_size_mb(file_path: Path) -> float:
        if file_path.exists():
            return file_path.stat().st_size / 1024 / 1024
        return 0

    def _print_step_failures(self, details: dict[str, Any], step: str) -> None:
        for name, item in details.items():
            if item.get("success") or item.get("skipped"):
                continue
            code = item.get("error_code", "error")
            message = item.get("message", "Operation failed")
            print(f"  ⚠️  {step} — {name} ({code}): {message}")

    def _finalize_step_result(
        self,
        details: dict[str, Any],
        targets: List[str],
    ) -> dict[str, Any]:
        summary = summarize_details(details)
        if summary["partial"]:
            parts: list[str] = []
            if summary["succeeded"]:
                parts.append(f"restored={summary['succeeded']}")
            if summary["skipped"]:
                parts.append(f"skipped={summary['skipped']}")
            if summary["failed"]:
                parts.append(f"failed={summary['failed']}")
            print(f"\nPartial success: {', '.join(parts)}")
        elif summary["success"]:
            if summary["skipped"] and not summary["succeeded"]:
                print(f"\nAll selected databases skipped: {summary['skipped']}")
            else:
                print("\nStep succeeded for all selected databases")
        else:
            print("\nStep failed for all selected databases")
        self._print_step_failures(details, "detail")
        return {
            "success": summary["success"],
            "partial": summary["partial"],
            "summary": summary,
            "details": details,
            "targets": targets,
        }

    def check_connectivity(self, database_names: List[str]) -> list[dict[str, Any]]:
        targets = self.config_service.validate_database_targets(database_names)
        backup_mgr = BackupManager(max_age_days=self.settings.backup_max_age_days)
        results: list[dict[str, Any]] = []

        for db in backup_mgr.config.get("databases", []):
            if not matches_database_targets(db, targets):
                continue
            if not db.get("enabled", True):
                results.append(
                    {
                        "name": db["name"],
                        "reachable": False,
                        "error_code": "disabled",
                        "message": "Database is disabled in configuration",
                    }
                )
                continue

            try:
                conn_string = backup_mgr.resolve_connection_string(db)
                pg_dump_path = backup_mgr.resolve_pg_tool(
                    db.get("source_config", {}).get("pg_dump_path", "pg_dump"),
                    "pg_dump",
                )
                ok, error_code, message = test_remote_connection(
                    conn_string,
                    pg_dump_path,
                    timeout_seconds=self.settings.remote_connection_timeout_seconds,
                )
            except ValueError as exc:
                ok, error_code, message = False, "missing_credentials", str(exc)

            results.append(
                {
                    "name": db["name"],
                    "reachable": ok,
                    "error_code": error_code or None,
                    "message": message or None,
                }
            )

        return results

    def check_local_postgres(self) -> dict[str, Any]:
        backup_mgr = BackupManager(max_age_days=self.settings.backup_max_age_days)
        local = resolve_local_db_config(self.settings, backup_mgr.config)
        ok, error_code, message = test_local_connection(
            local,
            timeout_seconds=self.settings.local_connection_timeout_seconds,
        )
        return {
            "reachable": ok,
            "host": local["host"],
            "port": local["port"],
            "username": local["username"],
            "error_code": error_code or None,
            "message": message or None,
        }

    def run_backup(self, request: JobRequest) -> dict[str, Any]:
        targets = self._resolve_targets(request)
        print(f"\n{'=' * 60}")
        print("BACKUP OPERATION")
        print(f"{'=' * 60}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Targets: {', '.join(targets)}")

        mgr = BackupManager(max_age_days=self.settings.backup_max_age_days)
        details = mgr.backup_all(force=request.force_backup, target_names=targets)
        return self._finalize_step_result(details, targets)

    def run_restore(self, request: JobRequest) -> dict[str, Any]:
        targets = self._resolve_targets(request)
        print(f"\n{'=' * 60}")
        print("RESTORE OPERATION")
        print(f"{'=' * 60}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Targets: {', '.join(targets)}")

        mgr = RestoreManager(
            restore_cooldown_days=self.settings.restore_cooldown_days,
            skip_recent_restore=not request.force_restore,
        )
        details = mgr.restore_all(force=request.force_restore, target_names=targets)
        return self._finalize_step_result(details, targets)

    def run_validation(
        self,
        request: JobRequest,
        targets_override: Optional[List[str]] = None,
    ) -> dict[str, Any]:
        targets = targets_override if targets_override is not None else self._resolve_targets(request)
        if request.full_validation:
            success = run_full_validation(target_names=targets)
        else:
            success = run_quick_validation(target_names=targets)
        return {
            "success": success,
            "type": "full" if request.full_validation else "quick",
            "targets": targets,
        }

    def run_pipeline(self, request: JobRequest) -> dict[str, Any]:
        targets = self._resolve_targets(request)
        print(f"\n{'=' * 60}")
        print("FULL PIPELINE: BACKUP -> RESTORE -> VALIDATE")
        print(f"{'=' * 60}")
        print(f"Targets: {', '.join(targets)}")

        steps: dict[str, Any] = {}
        partial = False
        any_success = False

        if not request.skip_backup:
            backup_result = self.run_backup(request)
            steps["backup"] = backup_result
            partial = partial or backup_result.get("partial", False)
            any_success = any_success or backup_result.get("success", False)

            if not backup_result.get("success"):
                if self._any_dump_available(targets):
                    print(
                        "\nSome remote backups failed (often IP restrictions). "
                        "Continuing restore using existing local dumps where available."
                    )
                else:
                    message = (
                        "All remote backups failed and no local dumps exist for the "
                        "selected databases."
                    )
                    print(f"\n❌ {message}")
                    return {
                        "success": False,
                        "partial": False,
                        "steps": steps,
                        "targets": targets,
                        "message": message,
                    }
        else:
            steps["backup"] = {"skipped": True, "success": True}

        if not request.skip_restore:
            restore_result = self.run_restore(request)
            steps["restore"] = restore_result
            partial = partial or restore_result.get("partial", False)
            any_success = any_success or restore_result.get("success", False)
        else:
            steps["restore"] = {"skipped": True, "success": True}

        if not request.skip_validation:
            restore_step = steps.get("restore", {})
            if restore_step.get("skipped"):
                validation_result = self.run_validation(request)
            else:
                restore_summary = restore_step.get("summary", {})
                restored = restore_summary.get("succeeded") or []
                skipped_restores = restore_summary.get("skipped") or []
                failed_restores = restore_summary.get("failed") or []
                if restored:
                    if failed_restores:
                        print(
                            f"\nValidating only successfully restored databases: "
                            f"{', '.join(restored)}"
                        )
                        print(
                            f"Skipped validation for failed restores ({', '.join(failed_restores)}) — "
                            "those databases may still contain previous data."
                        )
                    validation_result = self.run_validation(
                        request,
                        targets_override=restored,
                    )
                elif skipped_restores:
                    print(
                        f"\nNo new restores performed; validating existing local databases: "
                        f"{', '.join(skipped_restores)}"
                    )
                    if failed_restores:
                        print(
                            f"Skipped validation for failed restores ({', '.join(failed_restores)}) — "
                            "those databases may still contain previous data."
                        )
                    validation_result = self.run_validation(
                        request,
                        targets_override=skipped_restores,
                    )
                else:
                    print("\nNo databases were restored successfully; skipping validation.")
                    validation_result = {
                        "success": False,
                        "skipped": True,
                        "type": "full" if request.full_validation else "quick",
                        "targets": [],
                    }
            steps["validation"] = validation_result
            any_success = any_success or validation_result.get("success", False)
        else:
            steps["validation"] = {"skipped": True, "success": True}

        overall_success = any_success
        return {
            "success": overall_success,
            "partial": partial,
            "steps": steps,
            "targets": targets,
        }

    def execute(self, request: JobRequest) -> dict[str, Any]:
        if request.operation == OperationType.pipeline:
            return self.run_pipeline(request)
        if request.operation == OperationType.backup:
            return self.run_backup(request)
        if request.operation == OperationType.restore:
            return self.run_restore(request)
        return self.run_validation(request)
