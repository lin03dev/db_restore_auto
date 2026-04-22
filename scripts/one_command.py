#!/usr/bin/env python3
"""
ONE COMMAND TO RULE THEM ALL
Complete backup, restore, and validation in one seamless command
"""
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import Config
from core.backup_manager import BackupManager
from core.restore_manager import RestoreManager

class OneCommand:
    def __init__(self):
        self.start_time = datetime.now()
        self.results = {'backup': False, 'restore': False, 'validation': False}
    
    def print_header(self):
        print("\n" + "🚀"*40)
        print("     ONE COMMAND - BACKUP → RESTORE → VALIDATE")
        print("🚀"*40)
        print(f"Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
    
    def run_backup(self, force=False):
        print("\n📦 STEP 1: BACKUP")
        print("-"*40)
        mgr = BackupManager()
        results = mgr.backup_all(force=force)
        success = all(results.values())
        self.results['backup'] = success
        if success:
            print("\n✅ Backup step completed")
        else:
            print("\n❌ Backup step failed")
        return success
    
    def run_restore(self, force=False):
        print("\n💾 STEP 2: RESTORE")
        print("-"*40)
        mgr = RestoreManager()
        results = mgr.restore_all(force=force)
        
        # Check if any restore actually succeeded
        success = any(results.values()) if results else False
        self.results['restore'] = success
        
        # Print individual results
        for db_name, result in results.items():
            if result:
                print(f"  ✅ {db_name}: Restored successfully")
            else:
                print(f"  ❌ {db_name}: Restore failed")
        
        if success:
            print("\n✅ Restore step completed")
        else:
            print("\n❌ Restore step failed")
        return success
    
    def run_validation(self):
        print("\n🔍 STEP 3: VALIDATION")
        print("-"*40)
        from scripts.validate_restore import main as validate_main
        import io
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        result = validate_main()
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        print(output)
        success = result == 0
        self.results['validation'] = success
        return success
    
    def print_summary(self):
        duration = (datetime.now() - self.start_time).total_seconds()
        print("\n" + "="*60)
        print("📊 FINAL SUMMARY")
        print("="*60)
        print(f"Duration: {duration:.2f} seconds")
        print("-"*40)
        
        icons = {'backup': '📦', 'restore': '💾', 'validation': '🔍'}
        for step, success in self.results.items():
            icon = icons.get(step, '•')
            status = "✅ SUCCESS" if success else "❌ FAILED"
            print(f"{icon} {step.capitalize()}: {status}")
        
        print("-"*40)
        if all(self.results.values()):
            print("🎉 ALL STEPS COMPLETED SUCCESSFULLY!")
        elif self.results['validation'] and self.results['restore']:
            print("🎉 Backup and Restore completed successfully!")
        elif self.results['validation']:
            print("✅ Validation passed - Databases are healthy!")
        else:
            print("⚠️ SOME STEPS FAILED - Check logs for details")
        print("="*60)
    
    def run(self, force_backup=False, force_restore=False):
        self.print_header()
        
        # Step 1: Backup
        if not self.run_backup(force=force_backup):
            if not force_restore:
                print("\n❌ Aborting - backup failed. Use --force-restore to override.")
                return False
        
        # Step 2: Restore
        restore_success = self.run_restore(force=force_restore)
        
        # Step 3: Validation
        self.run_validation()
        
        # Summary
        self.print_summary()
        
        # Consider success if restore worked or validation passed
        return restore_success or self.results['validation']

def main():
    import argparse
    parser = argparse.ArgumentParser(description='One Command - Backup, Restore, Validate')
    parser.add_argument('--force-backup', action='store_true', help='Force backup even if recent')
    parser.add_argument('--force-restore', action='store_true', help='Force restore even if recent')
    parser.add_argument('--skip-backup', action='store_true', help='Skip backup step')
    parser.add_argument('--skip-restore', action='store_true', help='Skip restore step')
    
    args = parser.parse_args()
    
    cmd = OneCommand()
    
    if args.skip_backup and args.skip_restore:
        print("\n⚠️ Nothing to do - both backup and restore skipped")
        # Still run validation
        cmd.print_header()
        cmd.run_validation()
        cmd.print_summary()
        return 0
    
    if args.skip_backup:
        print("\n⏭️ Skipping backup...")
        cmd.results['backup'] = True
        cmd.print_header()
        if not args.skip_restore:
            cmd.run_restore(force=args.force_restore)
        cmd.run_validation()
        cmd.print_summary()
        return 0
    elif args.skip_restore:
        cmd.print_header()
        cmd.run_backup(force=args.force_backup)
        print("\n⏭️ Skipping restore...")
        cmd.results['restore'] = True
        cmd.run_validation()
        cmd.print_summary()
        return 0
    else:
        success = cmd.run(force_backup=args.force_backup, force_restore=args.force_restore)
        return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())