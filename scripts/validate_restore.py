#!/usr/bin/env python3
import sys
import os
import subprocess
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import Config
from utils.pg_tools import pg_tool_or_raise

def configured_databases():
    config_path = Config.BASE_DIR / "config" / "databases.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return [
        db["target_db"]
        for db in config.get("databases", [])
        if db.get("enabled", True)
    ]

def validate_database(db_name: str) -> tuple:
    env = os.environ.copy()
    env.update({"PGPASSWORD": Config.LOCAL_DB_CONFIG['password']})
    
    # Check table count
    try:
        psql = pg_tool_or_raise("psql")
    except FileNotFoundError:
        return False, 0

    cmd = [psql, "-h", Config.LOCAL_DB_CONFIG['host'], "-p", str(Config.LOCAL_DB_CONFIG['port']),
           "-U", Config.LOCAL_DB_CONFIG['username'], "-d", db_name,
           "-tAc", "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';"]
    
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode == 0:
        table_count = result.stdout.strip()
        return True, int(table_count) if table_count else 0
    return False, 0

def main():
    print("\n" + "="*60)
    print("🔍 VALIDATION RESULTS")
    print("="*60)
    
    databases = configured_databases()
    all_valid = True
    
    for db in databases:
        success, tables = validate_database(db)
        if success and tables > 0:
            print(f"\n  ✅ {db}: {tables} tables")
        else:
            print(f"\n  ❌ {db}: No tables found")
            all_valid = False
    
    print("\n" + "="*60)
    if all_valid:
        print("✅ All databases validated successfully!")
    else:
        print("❌ Validation failed - some databases have no data")
    
    return 0 if all_valid else 1

if __name__ == "__main__":
    sys.exit(main())
