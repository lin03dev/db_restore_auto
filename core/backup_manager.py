import subprocess
import time
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import yaml
import threading

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import Config
from utils.pg_tools import find_pg_tool, pg_tool_or_raise

class ProgressBar:
    """Enhanced progress bar with ETA and speed"""
    
    def __init__(self, total_size_mb=None, description="Progress"):
        self.total_size_mb = total_size_mb
        self.description = description
        self.start_time = time.time()
        self.last_size = 0
        self.last_time = self.start_time
        self.current_size = 0
        self.speeds = []
        
    def update(self, current_size_mb, current_table=""):
        """Update progress bar"""
        self.current_size = current_size_mb
        now = time.time()
        elapsed = now - self.start_time
        
        # Calculate speed (moving average of last 5 samples)
        if now - self.last_time > 0:
            speed = (current_size_mb - self.last_size) / (now - self.last_time)
            self.speeds.append(speed)
            if len(self.speeds) > 5:
                self.speeds.pop(0)
            avg_speed = sum(self.speeds) / len(self.speeds)
        else:
            avg_speed = 0
        
        self.last_size = current_size_mb
        self.last_time = now
        
        # Calculate ETA
        if self.total_size_mb and avg_speed > 0:
            remaining_mb = max(0, self.total_size_mb - current_size_mb)
            eta_seconds = remaining_mb / avg_speed
            eta_str = self.format_time(eta_seconds)
        else:
            eta_str = "calculating..."
        
        # Calculate percentage
        if self.total_size_mb and self.total_size_mb > 0:
            percent = min(100, (current_size_mb / self.total_size_mb) * 100)
        else:
            percent = min(99, (current_size_mb / max(current_size_mb + 10, 1)) * 100)
        
        # Create progress bar
        bar_length = 50
        filled_length = int(bar_length * percent / 100)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        # Format sizes
        current_str = self.format_size(current_size_mb)
        total_str = self.format_size(self.total_size_mb) if self.total_size_mb else "unknown"
        speed_str = self.format_size(avg_speed)
        
        # Build progress line
        line = f"\r{self.description} │{bar}│ {percent:5.1f}% [{current_str}/{total_str}] {speed_str}/s ETA:{eta_str}"
        if current_table:
            table_display = current_table[:40] + "..." if len(current_table) > 40 else current_table
            line += f" │ {table_display}"
        
        sys.stdout.write(line)
        sys.stdout.flush()
    
    @staticmethod
    def format_size(size_mb):
        """Format size in appropriate units"""
        if size_mb < 1:
            return f"{size_mb * 1024:.1f}KB"
        elif size_mb < 1024:
            return f"{size_mb:.1f}MB"
        else:
            return f"{size_mb / 1024:.2f}GB"
    
    @staticmethod
    def format_time(seconds):
        """Format time in appropriate units"""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds/60:.1f}m"
        else:
            return f"{seconds/3600:.1f}h"
    
    def finish(self):
        """Mark progress as complete"""
        elapsed = time.time() - self.start_time
        sys.stdout.write(f"\r{self.description} │{'█' * 50}│ 100% [Complete in {self.format_time(elapsed)}]    \n")
        sys.stdout.flush()

class BackupManager:
    def __init__(self, config_path: str = "config/databases.yaml", max_age_days: int = 7):
        self.config_path = Path(config_path)
        self.config = self.load_config()
        self.max_age_days = max_age_days
        
    def load_config(self) -> Dict[str, Any]:
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def resolve_pg_tool(self, configured_path: str, tool_name: str) -> str:
        """Resolve PostgreSQL CLI tools across Linux-style and Windows paths."""
        return pg_tool_or_raise(tool_name, configured_path)

    def resolve_connection_string(self, db_config: Dict[str, Any]) -> str:
        source_config = db_config.get('source_config', {})
        conn_string = source_config.get('connection_string')
        if conn_string:
            return conn_string

        env_name = source_config.get('connection_string_env')
        if env_name:
            conn_string = os.getenv(env_name)
            if conn_string:
                return conn_string
            raise ValueError(
                f"Missing environment variable {env_name} for database {db_config.get('name')}"
            )

        raise ValueError(
            f"Missing source_config.connection_string for database {db_config.get('name')}"
        )
    
    def get_file_size_mb(self, file_path: Path) -> float:
        if file_path.exists():
            return file_path.stat().st_size / 1024 / 1024
        return 0
    
    def get_estimated_total_size(self, conn_string: str, pg_dump_path: str) -> float:
        """Estimate total database size in MB"""
        try:
            # Use psql to get database size
            psql_path = find_pg_tool(
                "psql",
                str(Path(pg_dump_path).with_name("psql")) if pg_dump_path else "psql",
            )
            if not psql_path:
                print("     Could not estimate size: psql was not found")
                return None
            cmd = [psql_path, conn_string, "-tAc", 
                   "SELECT pg_database_size(current_database()) / 1024 / 1024;"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception as e:
            print(f"     Could not estimate size: {e}")
        return None
    
    def format_size(self, size_mb: float) -> str:
        """Format size in appropriate units"""
        if size_mb < 1:
            return f"{size_mb * 1024:.1f} KB"
        elif size_mb < 1024:
            return f"{size_mb:.1f} MB"
        else:
            return f"{size_mb / 1024:.2f} GB"
    
    def needs_backup(self, dump_path: Path) -> bool:
        if not dump_path.exists() or dump_path.stat().st_size == 0:
            return True
        file_mtime = datetime.fromtimestamp(dump_path.stat().st_mtime)
        age_days = (datetime.now() - file_mtime).days
        return age_days >= self.max_age_days
    
    def execute_backup(self, db_config: Dict[str, Any], dump_path: Path, retry_count: int = 2) -> bool:
        db_name = db_config['name']
        conn_string = self.resolve_connection_string(db_config)
        configured_pg_dump = db_config.get('source_config', {}).get('pg_dump_path', 'pg_dump')
        pg_dump_path = self.resolve_pg_tool(configured_pg_dump, "pg_dump")
        
        print(f"\n  📦 Backing up {db_name}...")
        print(f"  🔧 Using pg_dump: {pg_dump_path}")
        
        # Try to estimate total size
        estimated_size_mb = self.get_estimated_total_size(conn_string, pg_dump_path)
        if estimated_size_mb:
            print(f"  📊 Estimated size: {self.format_size(estimated_size_mb)}")
        
        # Remove empty/incomplete dump file if exists
        if dump_path.exists() and dump_path.stat().st_size == 0:
            dump_path.unlink()
        
        for attempt in range(retry_count):
            if attempt > 0:
                print(f"     Retry attempt {attempt + 1}/{retry_count}...")
                time.sleep(5)
            
            # Build command
            cmd = [pg_dump_path, conn_string, "-F", "c", "-v", "-f", str(dump_path)]
            
            start_time = time.time()
            start_size = self.get_file_size_mb(dump_path) if dump_path.exists() else 0
            
            # Create progress bar
            progress = ProgressBar(estimated_size_mb, f"  {db_name}")
            current_table = "Starting..."
            
            try:
                # Execute and capture output
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                timeout = 7200  # 2 hour timeout
                last_update = time.time()
                
                # Thread for monitoring file size
                def monitor_file_size():
                    while process.poll() is None:
                        current_size = self.get_file_size_mb(dump_path)
                        progress.update(current_size, current_table)
                        time.sleep(1)
                
                # Start monitoring thread
                monitor_thread = threading.Thread(target=monitor_file_size, daemon=True)
                monitor_thread.start()
                
                # Read output to get table names
                for line in process.stdout:
                    if "dumping contents of table" in line.lower():
                        parts = line.split('"')
                        if len(parts) >= 2:
                            current_table = parts[1]
                    
                    # Check timeout
                    if time.time() - start_time > timeout:
                        print(f"\n     ⏰ Timeout after {timeout}s, killing process...")
                        process.kill()
                        break
                
                # Wait for completion
                return_code = process.wait()
                monitor_thread.join(timeout=1)
                
                # Final update
                final_size = self.get_file_size_mb(dump_path)
                progress.finish()
                
                # Check if backup succeeded
                if return_code == 0 and dump_path.exists() and dump_path.stat().st_size > 0:
                    total_time = time.time() - start_time
                    avg_speed = final_size / total_time if total_time > 0 else 0
                    
                    print(f"     ✅ Backup complete!")
                    print(f"        Final size: {self.format_size(final_size)}")
                    print(f"        Total time: {ProgressBar.format_time(total_time)}")
                    print(f"        Avg speed:  {ProgressBar.format_size(avg_speed)}/s")
                    return True
                else:
                    print(f"     ⚠️ Backup attempt {attempt + 1} failed (return code: {return_code})")
                    if dump_path.exists():
                        dump_path.unlink()
                        
            except KeyboardInterrupt:
                print(f"\n     ⚠️ Backup interrupted by user")
                if dump_path.exists():
                    dump_path.unlink()
                return False
            except Exception as e:
                print(f"     ⚠️ Exception during backup: {str(e)}")
                if dump_path.exists():
                    dump_path.unlink()
        
        print(f"     ❌ Backup failed after {retry_count} attempts")
        return False
    
    def backup_all(self, force: bool = False, target_name: Optional[str] = None) -> Dict[str, bool]:
        results = {}
        print(f"\n{'='*60}")
        print(f"📦 BACKUP OPERATION")
        print(f"{'='*60}")
        
        for db in self.config['databases']:
            if target_name and target_name != 'both':
                matches_name = db['name'].lower() == target_name.lower()
                matches_target = db.get('target_db', '').lower() == target_name.lower()
                if not matches_name and not matches_target:
                    continue

            if not db.get('enabled', True):
                print(f"\n  ⏭️  Skipping {db['name']} (disabled)")
                results[db['name']] = True
                continue
            
            dump_path = Config.DUMPS_DIR / db['source_dump']
            
            if force:
                print(f"\n  Force backup requested for {db['name']}")
                success = self.execute_backup(db, dump_path)
            elif self.needs_backup(dump_path):
                if dump_path.exists():
                    size = self.get_file_size_mb(dump_path)
                    print(f"\n  {db['name']} dump needs refresh ({self.format_size(size)}, {self.max_age_days} day limit)")
                else:
                    print(f"\n  No existing dump for {db['name']}")
                success = self.execute_backup(db, dump_path)
            else:
                size = self.get_file_size_mb(dump_path)
                age_days = (datetime.now() - datetime.fromtimestamp(dump_path.stat().st_mtime)).days
                print(f"\n  ✅ Using existing {db['name']} dump ({self.format_size(size)}, {age_days} days old)")
                success = True
            
            results[db['name']] = success
        
        return results
    
    def get_backup_summary(self) -> Dict[str, Any]:
        summary = {}
        for db in self.config['databases']:
            dump_path = Config.DUMPS_DIR / db['source_dump']
            exists = dump_path.exists() and dump_path.stat().st_size > 0
            summary[db['name']] = {
                'dump_file': str(dump_path),
                'exists': exists,
                'size_mb': self.get_file_size_mb(dump_path) if exists else 0,
                'age_days': (datetime.now() - datetime.fromtimestamp(dump_path.stat().st_mtime)).days if exists else None,
                'needs_refresh': self.needs_backup(dump_path) if exists else True
            }
        return summary
