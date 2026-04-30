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
        pg_dump_path = db_config['source_config'].get('pg_dump_path', '/usr/bin/pg_dump')
        
        print(f"\n  📦 Backing up {db_name}...")
        print(f"  🔧 Using pg_dump: {pg_dump_path}")
        
        # Remove empty/incomplete dump file if exists
        if dump_path.exists() and dump_path.stat().st_size == 0:
            dump_path.unlink()
        
        for attempt in range(retry_count):
            if attempt > 0:
                print(f"     Retry attempt {attempt + 1}/{retry_count}...")
                time.sleep(5)
            
            # Build command using list format (more reliable)
            cmd = [pg_dump_path, conn_string, "-F", "c", "-v", "-f", str(dump_path)]
            
            start_time = time.time()
            
            try:
                # Execute and capture output
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                
                last_size = 0
                last_update = start_time
                timeout = 7200  # 2 hour timeout
                
                # Read output for progress
                for line in process.stdout:
                    if "dumping contents" in line.lower():
                        table_name = line.split('"')[-2] if '"' in line else "tables"
                        sys.stdout.write(f'\r     Dumping: {table_name:<50}')
                        sys.stdout.flush()
                    
                    # Check file growth
                    current_size = self.get_file_size_mb(dump_path)
                    if time.time() - last_update >= 5 and current_size > last_size:
                        elapsed = time.time() - start_time
                        speed = current_size / elapsed if elapsed > 0 else 0
                        sys.stdout.write(f'\r     Progress: {current_size:.1f} MB at {speed:.1f} MB/s')
                        sys.stdout.flush()
                        last_size = current_size
                        last_update = time.time()
                    
                    # Check timeout
                    if time.time() - start_time > timeout:
                        print(f"\n     ⏰ Timeout after {timeout}s, killing process...")
                        process.kill()
                        break
                
                # Wait for completion
                return_code = process.wait()
                print()  # New line after progress
                
                # Check if backup succeeded
                if return_code == 0 and dump_path.exists() and dump_path.stat().st_size > 0:
                    size_mb = self.get_file_size_mb(dump_path)
                    print(f"     ✅ Backup complete: {size_mb:.1f} MB in {time.time() - start_time:.1f}s")
                    return True
                else:
                    print(f"     ⚠️ Backup attempt {attempt + 1} failed (return code: {return_code})")
                    if dump_path.exists():
                        dump_path.unlink()
                        
            except Exception as e:
                print(f"     ⚠️ Exception during backup: {str(e)}")
                if dump_path.exists():
                    dump_path.unlink()
        
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
    
    def get_backup_summary(self) -> Dict[str, Any]:
        """Get summary of all backups"""
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
