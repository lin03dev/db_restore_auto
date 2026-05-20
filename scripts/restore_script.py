#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.restore_manager import RestoreManager
from utils.logger import setup_logger

def main():
    parser = argparse.ArgumentParser(description='Database Restore Manager')
    parser.add_argument('--force', action='store_true', help='Force restore even if recently restored')
    parser.add_argument('--cooldown', type=int, default=7, help='Cooldown period in days (default: 7)')
    parser.add_argument('--status', action='store_true', help='Show restore status')
    parser.add_argument('--reset', action='store_true', help='Reset restore tracking')
    parser.add_argument('--database', '-d', default='both',
                        help='Database name or target DB from config/databases.yaml, or both')
    
    args = parser.parse_args()
    logger = setup_logger("restore")
    
    if args.reset:
        tracking_file = Path(__file__).parent.parent / ".restore_tracking.json"
        if tracking_file.exists():
            tracking_file.unlink()
            print("✅ Restore tracking reset")
        else:
            print("ℹ️ No tracking file found")
        return
    
    if args.status:
        manager = RestoreManager(restore_cooldown_days=args.cooldown)
        status = manager.get_restore_status()
        print("\n" + "="*60)
        print("RESTORE STATUS")
        print("="*60)
        for db, info in status.items():
            if info.get('last_restore'):
                last = datetime.fromisoformat(info['last_restore'])
                print(f"\n📊 {db}:")
                print(f"   Last restore: {last.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"   Days ago: {info['days_ago']}")
                print(f"   Can restore: {'✅ Yes' if info['can_restore'] else '⏸️ No'}")
            else:
                print(f"\n📊 {db}: ✅ Never restored")
        print("\n" + "="*60)
        return
    
    logger.info(f"Starting restore (cooldown: {args.cooldown} days)...")
    manager = RestoreManager(restore_cooldown_days=args.cooldown)
    results = manager.restore_all(force=args.force, target_name=args.database)
    
    print("\n" + "="*60)
    print("RESTORE RESULTS")
    print("="*60)
    for operation, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"{status}: {operation}")
    
    sys.exit(0 if all(results.values()) else 1)

if __name__ == "__main__":
    main()
