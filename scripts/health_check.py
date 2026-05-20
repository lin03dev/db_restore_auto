#!/usr/bin/env python3
"""
Check health of backups and databases
"""
import sys
import os
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

def main():
    print("\n" + "="*60)
    print("🏥 SYSTEM HEALTH CHECK")
    print("="*60)
    
    # Check dump files
    print("\n📦 Backup Files:")
    dump_dir = Config.DUMPS_DIR
    for dump_file in dump_dir.glob("*.dump"):
        if dump_file.stat().st_size > 0:
            size_mb = dump_file.stat().st_size / 1024 / 1024
            print(f"  ✅ {dump_file.name}: {size_mb:.1f} MB")
        else:
            print(f"  ❌ {dump_file.name}: EMPTY or CORRUPT")
    
    # Check local databases
    print("\n💾 Local Databases:")
    import subprocess
    env = os.environ.copy()
    env.update({"PGPASSWORD": Config.LOCAL_DB_CONFIG['password']})
    
    try:
        psql = pg_tool_or_raise("psql")
    except FileNotFoundError as e:
        print(f"  ❌ {e}")
        psql = None

    for db in configured_databases():
        if not psql:
            print(f"  ❌ {db}: psql not available")
            continue

        cmd = [psql, "-h", Config.LOCAL_DB_CONFIG['host'], 
               "-p", str(Config.LOCAL_DB_CONFIG['port']),
               "-U", Config.LOCAL_DB_CONFIG['username'], 
               "-d", db, "-tAc", 
               "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';"]
        
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if result.returncode == 0 and result.stdout.strip():
            table_count = result.stdout.strip()
            print(f"  ✅ {db}: {table_count} tables")
        else:
            print(f"  ❌ {db}: Not accessible or empty")
    
    print("\n" + "="*60)
    print("💡 Recommendations:")
    print("  • If backups are missing, run: run.bat --force")
    print("  • If databases are empty, run: run.bat --restore-only")
    print("="*60)

if __name__ == "__main__":
    main()
