import subprocess
import time
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import yaml
import json

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import Config

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
        """Verify database has tables after restore"""
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
        print(f"\n  📁 Restoring {target_db} ({size_mb:.1f} MB)...")
        
        env = {"PGPASSWORD": self.local.get('password', '')}
        cmd = ["pg_restore", "-h", self.local['host'], "-p", str(self.local['port']),
               "-U", self.local['username'], "--dbname", target_db, "--clean", 
               "--if-exists", "--no-owner", "--verbose", str(dump_path)]
        
        start_time = time.time()
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        
        last_update = start_time
        while process.poll() is None:
            if time.time() - last_update > 2:
                elapsed = time.time() - start_time
                sys.stdout.write(f'\r     Progress: {elapsed:.0f}s elapsed...')
                sys.stdout.flush()
                last_update = time.time()
            time.sleep(1)
        
        print(f'\r     ✅ Restore completed in {time.time() - start_time:.1f}s')
        
        # Check if restore was successful
        if process.returncode == 0:
            return True
        else:
            # pg_restore often returns non-zero for warnings but still works
            # Verify by checking if database has tables
            return self.verify_restore(target_db)
    
    def restore_all(self, force: bool = False) -> Dict[str, bool]:
        results = {}
        
        for db in self.config['databases']:
            if not db.get('enabled', True):
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
        """Get restore status for all databases"""
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
