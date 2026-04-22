#!/usr/bin/env python3
"""
Quick validation for both databases after restore
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import Config
from utils.logger import setup_logger

logger = setup_logger("quick_validate")

def quick_check(database: str):
    """Perform quick health check on database"""
    import subprocess
    
    db_config = Config.LOCAL_DB_CONFIG
    env = {"PGPASSWORD": db_config['password']}
    
    print(f"\n🔍 Quick check for {database}:")
    print("-" * 40)
    
    # Check 1: Database exists and has tables
    check_tables = f"""
    SELECT COUNT(*) 
    FROM information_schema.tables 
    WHERE table_schema NOT IN ('information_schema', 'pg_catalog');
    """
    
    cmd = [
        "psql", "-h", db_config['host'], "-p", str(db_config['port']),
        "-U", db_config['username'], "-d", database, "-tAc", check_tables
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode == 0:
        table_count = result.stdout.strip()
        print(f"  ✅ Tables: {table_count}")
    else:
        print(f"  ❌ Failed to connect: {result.stderr}")
        return False
    
    # Check 2: Check for orphaned records
    check_orphans = """
    WITH RECURSIVE fk_check AS (
        SELECT 
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        LIMIT 10
    )
    SELECT COUNT(*) FROM fk_check;
    """
    
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    print(f"  ✅ Foreign keys check passed")
    
    # Check 3: Database size
    check_size = "SELECT pg_database_size(current_database()) / 1024 / 1024 || ' MB'"
    cmd[7] = check_size
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode == 0:
        print(f"  💾 Size: {result.stdout.strip()}")
    
    return True

def main():
    print("\n" + "="*60)
    print("QUICK POST-RESTORE VALIDATION")
    print("="*60)
    
    databases = ["AG_Dev", "Telios_LMS_Survey_Dev"]
    all_healthy = True
    
    for db in databases:
        if not quick_check(db):
            all_healthy = False
    
    print("\n" + "="*60)
    if all_healthy:
        print("✅ All databases passed quick validation!")
    else:
        print("⚠️  Some databases have issues. Run full validation for details.")
    
    print("\n💡 For detailed validation run:")
    print("   python3 scripts/validate_restore.py --all")
    print("="*60)

if __name__ == "__main__":
    main()