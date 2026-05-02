import subprocess
import time
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import yaml
import json
import threading

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import Config

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
    def __init__(self, config_path: str = "config/databases.yaml", restore_cooldown_days: int = 7, skip_recent_restore: bool = False):
        self.config_path = Path(config_path)
        self.config = self.load_config()
        self.local = self.config.get('local_postgres', {})
        self.tracking_file = Config.BASE_DIR / ".restore_tracking.json"
        self.restore_cooldown_days = restore_cooldown_days
        self.skip_recent_restore = skip_recent_restore
        
    def load_config(self) -> Dict[str, Any]:
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
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
    
    def drop_database(self, db_name: str) -> bool:
        env = {"PGPASSWORD": self.local.get('password', '')}
        cmd = ["dropdb", "--if-exists", "-h", self.local['host'], "-p", str(self.local['port']), 
               "-U", self.local['username'], db_name]
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        return result.returncode == 0
    
    def create_database(self, db_name: str) -> bool:
        env = {"PGPASSWORD": self.local.get('password', '')}
        cmd = ["createdb", "-h", self.local['host'], "-p", str(self.local['port']),
               "-U", self.local['username'], "-O", self.local['username'], db_name]
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        return result.returncode == 0
    
    def verify_restore(self, db_name: str) -> bool:
        env = {"PGPASSWORD": self.local.get('password', '')}
        cmd = ["psql", "-h", self.local['host'], "-p", str(self.local['port']),
               "-U", self.local['username'], "-d", db_name,
               "-tAc", "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';"]
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if result.returncode == 0 and result.stdout.strip():
            table_count = int(result.stdout.strip())
            return table_count > 0
        return False
    
    def execute_restore(self, dump_path: Path, target_db: str) -> bool:
        size_mb = self.get_file_size_mb(dump_path)
        print(f"\n  📁 Restoring {target_db} ({self.format_size(size_mb)})...")
        
        env = {"PGPASSWORD": self.local.get('password', '')}
        cmd = ["pg_restore", "-h", self.local['host'], "-p", str(self.local['port']),
               "-U", self.local['username'], "--dbname", target_db, "--clean", 
               "--if-exists", "--no-owner", "--verbose", str(dump_path)]
        
        start_time = time.time()
        progress = RestoreProgressBar(f"  Restoring {target_db}")
        
        # Run restore process
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                   text=True, env=env, bufsize=1)
        
        last_update = start_time
        last_line = ""
        
        # Monitor progress
        while process.poll() is None:
            elapsed = time.time() - start_time
            progress.update(elapsed, last_line)
            time.sleep(1)
        
        # Check return code and verify
        success = process.returncode == 0 or self.verify_restore(target_db)
        progress.finish(success)
        
        if success:
            final_table_count = self.verify_table_count(target_db)
            print(f"     ✅ Restore successful! Tables: {final_table_count}")
            return True
        else:
            print(f"     ❌ Restore failed")
            return False
    
    def verify_table_count(self, db_name: str) -> int:
        env = {"PGPASSWORD": self.local.get('password', '')}
        cmd = ["psql", "-h", self.local['host'], "-p", str(self.local['port']),
               "-U", self.local['username'], "-d", db_name,
               "-tAc", "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';"]
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip())
        return 0
    
    def restore_all(self, force: bool = False) -> Dict[str, bool]:
        results = {}
        
        for db in self.config['databases']:
            if not db.get('enabled', True):
                print(f"\n  ⏭️  Skipping {db['name']} (disabled)")
                results[db['name']] = True
                continue
            
            dump_path = Config.DUMPS_DIR / db['source_dump']
            target_db = db['target_db']
            
            if not dump_path.exists() or dump_path.stat().st_size == 0:
                print(f"\n  ❌ Dump not found: {db['source_dump']}")
                results[db['name']] = False
                continue
            
            print(f"\n  🗑️  Dropping {target_db}...")
            self.drop_database(target_db)
            print(f"  🆕 Creating {target_db}...")
            self.create_database(target_db)
            
            success = self.execute_restore(dump_path, target_db)
            results[db['name']] = success
            
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
