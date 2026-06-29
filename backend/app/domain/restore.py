import json
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml

from app.core.config import Settings, get_settings
from app.domain.local_postgres import build_pg_env, resolve_local_db_config
from app.domain.results import failure_result, success_result
from app.domain.selection import matches_database_targets
from app.infrastructure.postgres_tools import pg_tool_or_raise


class RestoreProgressBar:
    """Progress bar for restore operations"""
    
    def __init__(self, description="Restoring"):
        self.description = description
        self.start_time = time.time()
        
    def update(self, elapsed, step_info=""):
        """Update progress bar"""
        bar_length = 50
        elapsed_str = self.format_time(elapsed)
        
        # Create spinner for indeterminate progress
        spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        frame = int(elapsed * 10) % len(spinner)
        
        line = f"\r{self.description} {spinner[frame]} │ [{'░' * bar_length}] │ {elapsed_str} elapsed"
        if step_info:
            line += f" │ {step_info[:50]}"
        
        sys.stdout.write(line)
        sys.stdout.flush()
    
    @staticmethod
    def format_time(seconds):
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds/60:.1f}m"
        else:
            return f"{seconds/3600:.1f}h"
    
    def finish(self, success=True):
        elapsed = time.time() - self.start_time
        status = "✅" if success else "❌"
        sys.stdout.write(f"\r{self.description} {status} │{'█' * 50}│ Completed in {self.format_time(elapsed)}    \n")
        sys.stdout.flush()

class RestoreManager:
    def __init__(
        self,
        config_path: Optional[str] = None,
        restore_cooldown_days: Optional[int] = None,
        skip_recent_restore: bool = True,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        self.config_path = Path(config_path) if config_path else self.settings.databases_config
        self.config = self.load_config()
        self.local = resolve_local_db_config(self.settings, self.config)
        self.tracking_file = self.settings.base_dir / ".restore_tracking.json"
        self.restore_cooldown_days = (
            restore_cooldown_days
            if restore_cooldown_days is not None
            else self.settings.restore_cooldown_days
        )
        self.skip_recent_restore = skip_recent_restore
        
    def load_config(self) -> Dict[str, Any]:
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def resolve_pg_tool(self, tool_name: str) -> str:
        return pg_tool_or_raise(tool_name)
    
    def get_file_size_mb(self, file_path: Path) -> float:
        if file_path.exists():
            return file_path.stat().st_size / 1024 / 1024
        return 0
    
    def format_size(self, size_mb: float) -> str:
        if size_mb < 1:
            return f"{size_mb * 1024:.1f} KB"
        elif size_mb < 1024:
            return f"{size_mb:.1f} MB"
        else:
            return f"{size_mb / 1024:.2f} GB"
    
    def _sql_literal(self, value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    def terminate_database_connections(self, db_name: str) -> None:
        sql = (
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE datname = {self._sql_literal(db_name)} "
            "AND pid <> pg_backend_pid();"
        )
        cmd = [
            self.resolve_pg_tool("psql"),
            "-h",
            self.local["host"],
            "-p",
            str(self.local["port"]),
            "-U",
            self.local["username"],
            "-d",
            "postgres",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            sql,
        ]
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=build_pg_env(self.local),
        )

    def drop_database(self, db_name: str) -> Tuple[bool, str, str]:
        from app.domain.connectivity import classify_connection_error

        print(f"     Closing active connections to {db_name}...")
        self.terminate_database_connections(db_name)
        time.sleep(0.5)

        base_cmd = [
            self.resolve_pg_tool("dropdb"),
            "--if-exists",
            "--force",
            "-h",
            self.local["host"],
            "-p",
            str(self.local["port"]),
            "-U",
            self.local["username"],
            db_name,
        ]
        result = subprocess.run(
            base_cmd, capture_output=True, text=True, env=build_pg_env(self.local)
        )
        if result.returncode == 0:
            return True, "", ""

        # Older dropdb builds may not support --force; retry after terminating sessions.
        if "unrecognized option" in (result.stderr or "").lower():
            retry_cmd = [arg for arg in base_cmd if arg != "--force"]
            self.terminate_database_connections(db_name)
            time.sleep(0.5)
            result = subprocess.run(
                retry_cmd, capture_output=True, text=True, env=build_pg_env(self.local)
            )
            if result.returncode == 0:
                return True, "", ""

        code, message = classify_connection_error(result.stderr, result.stdout)
        return False, code, message

    def create_database(self, db_name: str) -> Tuple[bool, str, str]:
        from app.domain.connectivity import classify_connection_error

        cmd = [
            self.resolve_pg_tool("createdb"),
            "-h",
            self.local["host"],
            "-p",
            str(self.local["port"]),
            "-U",
            self.local["username"],
            "-O",
            self.local["username"],
            db_name,
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, env=build_pg_env(self.local)
        )
        if result.returncode == 0:
            return True, "", ""
        code, message = classify_connection_error(result.stderr, result.stdout)
        return False, code, message
    
    def verify_restore(self, db_name: str) -> bool:
        cmd = [
            self.resolve_pg_tool("psql"),
            "-h",
            self.local["host"],
            "-p",
            str(self.local["port"]),
            "-U",
            self.local["username"],
            "-d",
            db_name,
            "-tAc",
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema NOT IN ('information_schema', 'pg_catalog');",
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, env=build_pg_env(self.local)
        )
        if result.returncode == 0 and result.stdout.strip():
            table_count = int(result.stdout.strip())
            return table_count > 0
        return False
    
    def execute_restore(self, dump_path: Path, target_db: str) -> bool:
        size_mb = self.get_file_size_mb(dump_path)
        print(f"\n  📁 Restoring {target_db} ({self.format_size(size_mb)})...")
        
        env = build_pg_env(self.local)
        cmd = [
            self.resolve_pg_tool("pg_restore"),
            "-h",
            self.local["host"],
            "-p",
            str(self.local["port"]),
            "-U",
            self.local["username"],
            "--dbname",
            target_db,
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-acl",
            "--verbose",
            str(dump_path),
        ]
        
        start_time = time.time()
        progress = RestoreProgressBar(f"  Restoring {target_db}")
        
        # Run restore process
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, env=env, bufsize=1, errors="replace")
        
        last_line = ""
        output_tail = deque(maxlen=30)

        def read_restore_output():
            nonlocal last_line
            if not process.stdout:
                return
            for line in process.stdout:
                clean_line = line.strip()
                if clean_line:
                    last_line = clean_line
                    output_tail.append(clean_line)

        output_thread = threading.Thread(target=read_restore_output, daemon=True)
        output_thread.start()

        # Monitor progress
        while process.poll() is None:
            elapsed = time.time() - start_time
            progress.update(elapsed, last_line)
            time.sleep(1)

        output_thread.join(timeout=5)

        # Check return code and verify
        final_table_count = self.verify_table_count(target_db)
        success = final_table_count > 0
        progress.finish(success)
        
        if success:
            if process.returncode != 0:
                print(f"     WARNING: pg_restore exited with code {process.returncode}, but tables were found")
                if output_tail:
                    print("     Last pg_restore output:")
                    for line in list(output_tail)[-10:]:
                        print(f"       {line}")
            print(f"     ✅ Restore successful! Tables: {final_table_count}")
            return True
        else:
            print(f"     Restore failed (pg_restore exit code: {process.returncode})")
            if output_tail:
                print("     Last pg_restore output:")
                for line in list(output_tail)[-15:]:
                    print(f"       {line}")
            print(f"     ❌ Restore failed")
            return False
    
    def verify_table_count(self, db_name: str) -> int:
        cmd = [
            self.resolve_pg_tool("psql"),
            "-h",
            self.local["host"],
            "-p",
            str(self.local["port"]),
            "-U",
            self.local["username"],
            "-d",
            db_name,
            "-tAc",
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema NOT IN ('information_schema', 'pg_catalog');",
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, env=build_pg_env(self.local)
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip())
        return 0
    
    def restore_all(
        self,
        force: bool = False,
        target_names: Optional[list[str]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        results: Dict[str, Dict[str, Any]] = {}
        restore_status = self.get_restore_status()
        if target_names:
            print(f"\n  Selected for restore: {', '.join(target_names)}")

        from app.domain.local_postgres import test_local_connection

        local_ok, local_code, local_message = test_local_connection(
            self.local,
            timeout_seconds=self.settings.local_connection_timeout_seconds,
        )
        if not local_ok:
            print(f"\n  ❌ Local PostgreSQL unavailable ({local_code}): {local_message}")
            for db in self.config["databases"]:
                if not matches_database_targets(db, target_names):
                    continue
                if not db.get("enabled", True):
                    continue
                results[db["name"]] = failure_result(local_code, local_message)
            return results
        
        for db in self.config['databases']:
            if not matches_database_targets(db, target_names):
                continue

            if not db.get('enabled', True):
                print(f"\n  ⏭️  Skipping {db['name']} (disabled)")
                results[db['name']] = success_result(skipped=True)
                continue
            
            dump_path = self.settings.dumps_dir / db['source_dump']
            target_db = db['target_db']

            if self.skip_recent_restore and not force:
                db_status = restore_status.get(target_db, {})
                if not db_status.get('can_restore', True):
                    print(
                        f"\n  ⏸️  Skipping {target_db} "
                        f"(restored {db_status.get('days_ago')} days ago; "
                        f"cooldown is {self.restore_cooldown_days} days)"
                    )
                    results[db['name']] = success_result(
                        skipped=True,
                        reason="restore_cooldown",
                    )
                    continue

            if not dump_path.exists() or dump_path.stat().st_size == 0:
                print(f"\n  ❌ Dump not found: {db['source_dump']}")
                results[db['name']] = failure_result(
                    "dump_missing",
                    "No local dump available. Remote backup may have failed due to IP restrictions.",
                )
                continue
            
            print(f"\n  🗑️  Dropping {target_db}...")
            dropped, drop_code, drop_message = self.drop_database(target_db)
            if not dropped:
                print(f"  ❌ Could not drop {target_db}: {drop_message}")
                results[db["name"]] = failure_result(drop_code, drop_message)
                continue

            print(f"  🆕 Creating {target_db}...")
            created, create_code, create_message = self.create_database(target_db)
            if not created:
                print(f"  ❌ Could not create {target_db}: {create_message}")
                results[db["name"]] = failure_result(create_code, create_message)
                continue
            
            success = self.execute_restore(dump_path, target_db)
            results[db['name']] = (
                success_result()
                if success
                else failure_result("restore_failed", "pg_restore did not complete successfully")
            )

            if success:
                print(f"  ✅ {db['name']} restore successful")
                self.save_tracking(target_db)
            else:
                print(f"  ❌ {db['name']} restore failed")
        
        return results
    
    def save_tracking(self, db_name: str):
        tracking = {}
        if self.tracking_file.exists():
            with open(self.tracking_file, 'r') as f:
                tracking = json.load(f)
        tracking[db_name] = datetime.now().isoformat()
        with open(self.tracking_file, 'w') as f:
            json.dump(tracking, f, indent=2)
    
    def get_restore_status(self) -> Dict[str, Any]:
        status = {}
        tracking = {}
        if self.tracking_file.exists():
            with open(self.tracking_file, 'r') as f:
                tracking = json.load(f)
        
        for db in self.config['databases']:
            target_db = db['target_db']
            last_restore = tracking.get(target_db)
            if last_restore:
                last_date = datetime.fromisoformat(last_restore)
                days_ago = (datetime.now() - last_date).days
                status[target_db] = {
                    'last_restore': last_restore,
                    'days_ago': days_ago,
                    'can_restore': days_ago >= self.restore_cooldown_days
                }
            else:
                status[target_db] = {
                    'last_restore': None,
                    'days_ago': None,
                    'can_restore': True
                }
        return status
