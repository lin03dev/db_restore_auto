import argparse
import json
from datetime import datetime
from typing import List, Optional

from app.core.config import get_settings
from app.schemas import JobRequest, OperationType
from app.services.orchestrator import OrchestratorService


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Database backup, restore, and validation pipeline",
    )
    parser.add_argument("--skip-backup", action="store_true")
    parser.add_argument("--skip-restore", action="store_true")
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument("--force-backup", action="store_true")
    parser.add_argument("--force-restore", action="store_true")
    parser.add_argument("--no-backup-check", action="store_true")
    parser.add_argument("--no-restore-check", action="store_true")
    parser.add_argument(
        "--databases",
        default="",
        help="Comma-separated database names (default: all enabled)",
    )
    parser.add_argument("--database", "-d", default=None, help="Deprecated: use --databases")
    parser.add_argument("--full-validation", action="store_true")
    parser.add_argument("--quick-validation", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--reset", action="store_true")
    return parser


def _print_status(service: OrchestratorService) -> None:
    status = service.get_status()
    print("\nCURRENT STATUS")
    print("=" * 60)
    for backup in status.backups:
        label = "fresh" if not backup.needs_refresh else "needs refresh"
        print(f"  {backup.name}: {backup.age_days} days ({label}), dump={backup.dump_file}")
    for restore in status.restores:
        print(f"  {restore.target_db}: {restore.status}")
    print("=" * 60)


def _parse_databases(args: argparse.Namespace) -> List[str]:
    if args.databases:
        return [item.strip() for item in args.databases.split(",") if item.strip()]
    if args.database and args.database.lower() != "both":
        return [args.database.strip()]
    return []


def _args_to_request(args: argparse.Namespace) -> JobRequest:
    if not args.full_validation and not args.quick_validation:
        args.quick_validation = True
    return JobRequest(
        operation=OperationType.pipeline,
        databases=_parse_databases(args),
        force_backup=args.force_backup or args.no_backup_check,
        force_restore=args.force_restore or args.no_restore_check,
        skip_backup=args.skip_backup,
        skip_restore=args.skip_restore,
        skip_validation=args.skip_validation,
        full_validation=args.full_validation,
    )


def run_cli(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = get_settings()
    service = OrchestratorService(settings)
    started_at = datetime.now()

    if args.status:
        _print_status(service)
        return 0

    if args.reset:
        print(service.reset_tracking()["message"])
        return 0

    request = _args_to_request(args)
    backup_result = (
        {"skipped": True, "success": True}
        if request.skip_backup
        else service.run_backup(request)
    )
    if not backup_result.get("success") and not request.force_restore and not request.skip_restore:
        print("\nBackup failed. Continue with restore? (y/N): ", end="")
        if input().lower() != "y":
            return 1

    restore_result = (
        {"skipped": True, "success": True}
        if request.skip_restore
        else service.run_restore(request)
    )
    validation_result = (
        {"skipped": True, "success": True}
        if request.skip_validation
        else service.run_validation(request)
    )

    results = {
        "success": all(
            step.get("success", False) or step.get("skipped")
            for step in (backup_result, restore_result, validation_result)
        ),
        "backup": backup_result,
        "restore": restore_result,
        "validation": validation_result,
    }

    report_dir = settings.logs_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / f"cli_report_{started_at.strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w") as handle:
        json.dump({"timestamp": started_at.isoformat(), "results": results}, handle, indent=2)

    print(f"\nReport saved: {report_file}")
    return 0 if results["success"] else 1
