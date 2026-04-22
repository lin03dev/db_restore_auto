import subprocess
import time
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import Config

class BackupManager:
    def __init__(self, config_path: str = "config/databases.yaml", max_age_days: int = 7):
        self.config_path = Path(config_path)
        self.config = self.load_config()
        self.max_age_days = max_age_days
        
    def load_config(self) -> Dict[str, Any]:
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def get_file_size_mb(self, file_path: Path) -> float:
        if file_path.exists():
            return file_path.stat().st_size / 1024 / 1024
        return 0
    
    def needs_backup(self, dump_path: Path) -> bool:
        if not dump_path.exists() or dump_path.stat().st_size == 0:
            return True
        file_mtime = datetime.fromtimestamp(dump_path.stat().st_mtime)
        age_days = (datetime.now() - file_mtime).days
        return age_days >= self.max_age_days
    
    def execute_backup(self, db_config: Dict[str, Any], dump_path: Path, retry_count: int = 2) -> bool:
        db_name = db_config['name']
        conn_string = db_config['source_config']['connection_string']
        
        print(f"\n  📦 Backing up {db_name}...")
        
        # Remove empty/incomplete dump file if exists
        if dump_path.exists() and dump_path.stat().st_size == 0:
            dump_path.unlink()
        
        for attempt in range(retry_count):
            if attempt > 0:
                print(f"     Retry attempt {attempt + 1}/{retry_count}...")
                time.sleep(5)  # Wait before retry
            
            # Build command
            if db_name == "AG":
                cmd = f"pg_dump '{conn_string}' -F c -v -f {dump_path}"
            else:
                pg_dump_path = db_config['source_config'].get('pg_dump_path', '/usr/lib/postgresql/16/bin/pg_dump')
                cmd = f"{pg_dump_path} '{conn_string}' -F c -v -f {dump_path}"
            
            start_time = time.time()
            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            last_size = 0
            last_update = start_time
            timeout = 7200  # 2 hour timeout for AG
            
            while process.poll() is None:
                current_size = self.get_file_size_mb(dump_path)
                
                # Update progress every 2 seconds
                if time.time() - last_update >= 2:
                    if current_size > last_size:
                        elapsed = time.time() - start_time
                        speed = current_size / elapsed if elapsed > 0 else 0
                        max_size = 5000 if db_name == "AG" else 50
                        percent = min(100, int((current_size / max_size) * 100))
                        bar_len = 30
                        filled = int(bar_len * percent / 100)
                        bar = '█' * filled + '░' * (bar_len - filled)
                        sys.stdout.write(f'\r     |{bar}| {percent}% ({current_size:.1f} MB) - {speed:.1f} MB/s')
                        sys.stdout.flush()
                        last_size = current_size
                    last_update = time.time()
                
                # Check timeout
                if time.time() - start_time > timeout:
                    print(f"\n     ⏰ Timeout after {timeout}s, killing process...")
                    process.kill()
                    break
                
                time.sleep(1)
            
            print()  # New line after progress
            
            # Check if backup succeeded
            if process.returncode == 0 and dump_path.exists() and dump_path.stat().st_size > 0:
                size_mb = self.get_file_size_mb(dump_path)
                print(f"     ✅ Backup complete: {size_mb:.1f} MB in {time.time() - start_time:.1f}s")
                return True
            else:
                print(f"     ⚠️ Backup attempt {attempt + 1} failed")
                if dump_path.exists():
                    dump_path.unlink()  # Remove partial file
        
        print(f"     ❌ Backup failed after {retry_count} attempts")
        return False
    
    def backup_all(self, force: bool = False) -> Dict[str, bool]:
        results = {}
        print(f"\n{'='*60}")
        print(f"📦 BACKUP OPERATION")
        print(f"{'='*60}")
        
        for db in self.config['databases']:
            if not db.get('enabled', True):
                continue
            
            dump_path = Config.DUMPS_DIR / db['source_dump']
            
            # Check if backup is needed
            if force:
                print(f"\n  Force backup requested for {db['name']}")
                success = self.execute_backup(db, dump_path)
            elif self.needs_backup(dump_path):
                if dump_path.exists():
                    size = self.get_file_size_mb(dump_path)
                    print(f"\n  {db['name']} dump needs refresh (current size: {size:.1f} MB)")
                else:
                    print(f"\n  No existing dump for {db['name']}")
                success = self.execute_backup(db, dump_path)
            else:
                size = self.get_file_size_mb(dump_path)
                print(f"\n  ✅ Using existing {db['name']} dump ({size:.1f} MB, {self.max_age_days} day max age)")
                success = True
            
            results[db['name']] = success
        
        return results