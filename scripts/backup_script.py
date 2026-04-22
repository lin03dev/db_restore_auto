#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.backup_manager import BackupManager
from utils.logger import setup_logger

def main():
    parser = argparse.ArgumentParser(description='Database Backup Manager')
    parser.add_argument('--force', action='store_true', help='Force backup even if recent')
    parser.add_argument('--max-age', type=int, default=7, help='Max age in days before new backup (default: 7)')
    parser.add_argument('--summary', action='store_true', help='Show backup summary')
    
    args = parser.parse_args()
    logger = setup_logger("backup")
    
    if args.summary:
        manager = BackupManager(max_age_days=args.max_age)
        summary = manager.get_backup_summary()
        print("\n" + "="*60)
        print("BACKUP SUMMARY")
        print("="*60)
        for db, info in summary.items():
            print(f"\n📊 {db}:")
            print(f"   File: {Path(info['dump_file']).name}")
            print(f"   Exists: {'✅' if info['exists'] else '❌'}")
            if info['exists']:
                print(f"   Age: {info['age_days']} days")
                print(f"   Size: {info['size_mb']:.2f} MB")
                print(f"   Needs refresh: {'⚠️ Yes' if info['needs_refresh'] else '✅ No'}")
        print("="*60)
        return
    
    logger.info(f"Starting backup (max age: {args.max_age} days)...")
    manager = BackupManager(max_age_days=args.max_age)
    results = manager.backup_all_databases(force=args.force)
    
    print("\n" + "="*60)
    print("BACKUP RESULTS")
    print("="*60)
    for db, result in results.items():
        status = "✅ SUCCESS" if result['success'] else "❌ FAILED"
        action = "🔄 New backup" if result.get('backup_performed') else "⏭️ Skipped (recent)"
        print(f"{status}: {db} - {action}")
    
    sys.exit(0 if all(r['success'] for r in results.values()) else 1)

if __name__ == "__main__":
    main()