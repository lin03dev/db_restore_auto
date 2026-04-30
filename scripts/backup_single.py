#!/usr/bin/env python3
"""
Backup a single database
Usage: python3 backup_single.py <database_name>
Example: python3 backup_single.py AG
         python3 backup_single.py Telios
"""
import sys
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.backup_manager import BackupManager
from config.settings import Config

def backup_single_database(db_name: str):
    # Load config
    with open('config/databases.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Find the database config
    db_config = None
    for db in config['databases']:
        if db['name'].lower() == db_name.lower():
            db_config = db
            break
    
    if not db_config:
        print(f"❌ Database '{db_name}' not found")
        print("\nAvailable databases:")
        for db in config['databases']:
            print(f"  - {db['name']}")
        return False
    
    print(f"\n{'='*60}")
    print(f"🎯 Backing up: {db_config['name']}")
    print(f"{'='*60}")
    
    manager = BackupManager()
    dump_path = Config.DUMPS_DIR / db_config['source_dump']
    
    # Remove empty dump if exists
    if dump_path.exists() and dump_path.stat().st_size == 0:
        print(f"⚠️ Removing empty dump file: {dump_path}")
        dump_path.unlink()
    
    success = manager.execute_backup(db_config, dump_path)
    
    if success:
        size_mb = dump_path.stat().st_size / 1024 / 1024
        print(f"\n✅ Backup completed successfully!")
        print(f"   File: {dump_path}")
        print(f"   Size: {size_mb:.2f} MB")
    else:
        print(f"\n❌ Backup failed for {db_config['name']}")
    
    return success

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/backup_single.py <database_name>")
        print("Example: python3 scripts/backup_single.py AG")
        print("         python3 scripts/backup_single.py Telios")
        sys.exit(1)
    
    success = backup_single_database(sys.argv[1])
    sys.exit(0 if success else 1)
