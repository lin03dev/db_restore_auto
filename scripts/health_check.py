#!/usr/bin/env python3
"""
Check health of backups and databases
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import Config

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
    env = {"PGPASSWORD": Config.LOCAL_DB_CONFIG['password']}
    
    for db in ["AG_Dev", "Telios_LMS_Survey_Dev"]:
        cmd = ["psql", "-h", Config.LOCAL_DB_CONFIG['host'], 
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
    print("  • If backups are missing, run: ./run.sh --force")
    print("  • If databases are empty, run: ./run.sh --restore-only")
    print("="*60)

if __name__ == "__main__":
    main()
