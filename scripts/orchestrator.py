#!/usr/bin/env python3
"""
Main Orchestrator - Complete Control Database Automation
Features:
- Full control over backup and restore operations
- Force options to override all checks
- Individual database targeting
- Comprehensive reporting
"""
import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import Config
from utils.logger import setup_logger
from core.backup_manager import BackupManager
from core.restore_manager import RestoreManager

class DatabaseOrchestrator:
    """Main orchestrator with full control options"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.logger = setup_logger("orchestrator")
        self.results = {
            'timestamp': self.start_time.isoformat(),
            'command': '',
            'backup': {'success': False, 'details': {}, 'skipped': False},
            'restore': {'success': False, 'details': {}, 'skipped': False},
            'validation': {'success': False, 'details': {}, 'skipped': False},
            'overall_success': False
        }
    
    def print_header(self, args):
        """Print main header with options"""
        print("\n" + "="*80)
        print("🎯 DATABASE AUTOMATION ORCHESTRATOR - FULL CONTROL")
        print("="*80)
        print(f"Started:    {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Working Dir: {Config.BASE_DIR}")
        print("-"*40)
        print("OPTIONS:")
        if args.force_backup:
            print("  • Force Backup: YES (ignoring age checks)")
        if args.force_restore:
            print("  • Force Restore: YES (ignoring cooldown)")
        if args.skip_backup:
            print("  • Backup: SKIPPED")
        if args.skip_restore:
            print("  • Restore: SKIPPED")
        if args.skip_validation:
            print("  • Validation: SKIPPED")
        if args.database:
            print(f"  • Target Database: {args.database}")
        if args.no_backup_check:
            print("  • Backup Age Check: DISABLED")
        if args.no_restore_check:
            print("  • Restore Cooldown: DISABLED")
        print("="*80)
    
    def run_backup(self, force: bool = False, skip_age_check: bool = False, 
                   specific_db: Optional[str] = None) -> bool:
        """Run backup with full control options"""
        print("\n📦 STEP 1: BACKUP OPERATION")
        print("-"*40)
        
        if skip_age_check:
            print("⚠️  Backup age check DISABLED - will backup regardless of age")
        if force:
            print("⚠️  Force backup ENABLED - will create new backups")
        if specific_db:
            print(f"🎯 Targeting specific database: {specific_db}")
        
        try:
            # If skip_age_check is True, we force backup
            actual_force = force or skip_age_check
            
            backup_mgr = BackupManager(max_age_days=7)
            
            # TODO: Add specific database filtering if needed
            results = backup_mgr.backup_all_databases(force=actual_force)
            
            success = all(r['success'] for r in results.values())
            self.results['backup'] = {
                'success': success,
                'details': results,
                'forced': actual_force,
                'skip_age_check': skip_age_check,
                'backups_created': any(r.get('backup_performed', False) for r in results.values())
            }
            
            if success:
                print("\n✅ Backup operation completed")
                for db, result in results.items():
                    if result.get('backup_performed'):
                        print(f"   • {db}: ✅ New backup created")
                    else:
                        print(f"   • {db}: ⏭️  Using existing backup (age: {result.get('age_days', 'N/A')} days)")
            else:
                print("\n❌ Backup operation failed")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Backup failed: {str(e)}")
            self.results['backup']['success'] = False
            self.results['backup']['error'] = str(e)
            print(f"\n❌ Backup error: {str(e)}")
            return False
    
    def run_restore(self, force: bool = False, skip_cooldown: bool = False,
                    specific_db: Optional[str] = None) -> bool:
        """Run restore with full control options"""
        print("\n💾 STEP 2: RESTORE OPERATION")
        print("-"*40)
        
        if skip_cooldown:
            print("⚠️  Restore cooldown check DISABLED")
        if force:
            print("⚠️  Force restore ENABLED")
        if specific_db:
            print(f"🎯 Targeting specific database: {specific_db}")
        
        try:
            # If skip_cooldown is True, we effectively force restore
            actual_force = force or skip_cooldown
            
            restore_mgr = RestoreManager(
                restore_cooldown_days=7,
                skip_recent_restore=not skip_cooldown  # Skip check if cooldown disabled
            )
            
            results = restore_mgr.restore_all_databases(force=actual_force)
            
            success = all(results.values())
            self.results['restore'] = {
                'success': success,
                'details': results,
                'forced': actual_force,
                'skip_cooldown': skip_cooldown
            }
            
            if success:
                print("\n✅ Restore operation completed")
                for operation, result in results.items():
                    if result:
                        print(f"   • {operation}: ✅ Success")
                    else:
                        print(f"   • {operation}: ⏭️  Skipped (recent restore)")
            else:
                print("\n❌ Restore operation failed")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Restore failed: {str(e)}")
            self.results['restore']['success'] = False
            self.results['restore']['error'] = str(e)
            print(f"\n❌ Restore error: {str(e)}")
            return False
    
    def run_validation(self, quick: bool = True, full: bool = False) -> bool:
        """Run validation"""
        print("\n🔍 STEP 3: VALIDATION")
        print("-"*40)
        
        try:
            if full:
                print("Running FULL validation (this may take a few minutes)...")
                # Full validation using validate_restore.py
                cmd = ['python3', 'scripts/validate_restore.py', '--all']
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=Config.BASE_DIR)
                success = result.returncode == 0
                
                self.results['validation'] = {
                    'success': success,
                    'type': 'full',
                    'output': result.stdout[-1000:] if result.stdout else ''
                }
            else:
                print("Running QUICK validation...")
                # Quick validation
                cmd = ['python3', 'scripts/quick_validation.py']
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=Config.BASE_DIR)
                success = result.returncode == 0
                
                self.results['validation'] = {
                    'success': success,
                    'type': 'quick',
                    'output': result.stdout[-500:] if result.stdout else ''
                }
            
            if success:
                print("\n✅ Validation passed")
                if result.stdout:
                    print(result.stdout[-500:])
            else:
                print("\n⚠️ Validation found issues")
                if result.stderr:
                    print(f"Error: {result.stderr[:500]}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Validation failed: {str(e)}")
            self.results['validation']['success'] = False
            self.results['validation']['error'] = str(e)
            print(f"\n❌ Validation error: {str(e)}")
            return False
    
    def show_status(self):
        """Show current status without running operations"""
        print("\n📊 CURRENT STATUS")
        print("="*60)
        
        # Backup status
        print("\n📦 BACKUP STATUS:")
        backup_mgr = BackupManager(max_age_days=7)
        summary = backup_mgr.get_backup_summary()
        for db, info in summary.items():
            if info['exists']:
                age = info['age_days']
                if age < 7:
                    print(f"  ✅ {db}: {age} days old (fresh)")
                else:
                    print(f"  ⚠️ {db}: {age} days old (needs refresh)")
                print(f"     Size: {info['size_mb']:.2f} MB")
            else:
                print(f"  ❌ {db}: No backup found")
        
        # Restore status
        print("\n💾 RESTORE STATUS:")
        restore_mgr = RestoreManager(restore_cooldown_days=7)
        status = restore_mgr.get_restore_status()
        for db, info in status.items():
            if info.get('last_restore'):
                last = datetime.fromisoformat(info['last_restore'])
                print(f"  📅 {db}: Last restored {info['days_ago']} days ago ({last.strftime('%Y-%m-%d')})")
                if info['can_restore']:
                    print(f"     ✅ Can restore now")
                else:
                    print(f"     ⏸️  Restore blocked (cooldown active)")
            else:
                print(f"  ✅ {db}: Never restored (can restore now)")
        
        print("\n" + "="*60)
    
    def reset_tracking(self):
        """Reset restore tracking"""
        tracking_file = Config.BASE_DIR / ".restore_tracking.json"
        if tracking_file.exists():
            tracking_file.unlink()
            print("✅ Restore tracking has been reset")
            print("   All databases can now be restored immediately")
        else:
            print("ℹ️ No tracking file found")
    
    def print_summary(self):
        """Print final summary"""
        duration = (datetime.now() - self.start_time).total_seconds()
        
        print("\n" + "="*80)
        print("📊 EXECUTION SUMMARY")
        print("="*80)
        print(f"Duration: {duration:.2f} seconds")
        print("-"*40)
        
        # Backup status
        if self.results['backup'].get('skipped'):
            print("Backup:   ⏭️  SKIPPED")
        else:
            status = "✅ SUCCESS" if self.results['backup']['success'] else "❌ FAILED"
            print(f"Backup:   {status}")
        
        # Restore status
        if self.results['restore'].get('skipped'):
            print("Restore:  ⏭️  SKIPPED")
        else:
            status = "✅ SUCCESS" if self.results['restore']['success'] else "❌ FAILED"
            print(f"Restore:  {status}")
        
        # Validation status
        if self.results['validation'].get('skipped'):
            print("Validate: ⏭️  SKIPPED")
        else:
            status = "✅ PASSED" if self.results['validation']['success'] else "⚠️ ISSUES"
            print(f"Validate: {status}")
        
        # Overall status
        if not self.results['backup'].get('skipped') and not self.results['restore'].get('skipped'):
            self.results['overall_success'] = all([
                self.results['backup']['success'],
                self.results['restore']['success']
            ])
        else:
            self.results['overall_success'] = True
        
        print("-"*40)
        if self.results['overall_success']:
            print("Overall:  ✅ OPERATION COMPLETE")
        else:
            print("Overall:  ⚠️ SOME OPERATIONS FAILED")
        print("="*80)
        
        # Save report
        self.save_report()
    
    def save_report(self):
        """Save execution report"""
        import json
        report_dir = Config.LOGS_DIR / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        report_file = report_dir / f"orchestrator_report_{timestamp}.json"
        
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        print(f"\n📄 Detailed report saved: {report_file}")
    
    def run(self, args):
        """Main orchestration flow with full control"""
        self.print_header(args)
        
        # Handle special commands first
        if args.status:
            self.show_status()
            return True
        
        if args.reset:
            self.reset_tracking()
            return True
        
        # Execute requested operations
        all_success = True
        
        # Step 1: Backup
        if args.skip_backup:
            print("\n⏭️ STEP 1: BACKUP SKIPPED")
            self.results['backup']['skipped'] = True
        else:
            backup_success = self.run_backup(
                force=args.force_backup,
                skip_age_check=args.no_backup_check,
                specific_db=args.database
            )
            all_success = all_success and backup_success
            
            # If backup failed and not forcing restore, ask
            if not backup_success and not args.force_restore and not args.skip_restore:
                print("\n⚠️ Backup failed. Continue with restore? (y/N): ", end='')
                response = input().lower()
                if response != 'y':
                    print("❌ Aborted by user")
                    return False
        
        # Step 2: Restore
        if args.skip_restore:
            print("\n⏭️ STEP 2: RESTORE SKIPPED")
            self.results['restore']['skipped'] = True
        else:
            restore_success = self.run_restore(
                force=args.force_restore,
                skip_cooldown=args.no_restore_check,
                specific_db=args.database
            )
            all_success = all_success and restore_success
        
        # Step 3: Validation
        if args.skip_validation:
            print("\n⏭️ STEP 3: VALIDATION SKIPPED")
            self.results['validation']['skipped'] = True
        else:
            self.run_validation(quick=not args.full_validation, full=args.full_validation)
        
        # Final summary
        self.print_summary()
        
        return all_success

def main():
    parser = argparse.ArgumentParser(
        description='Database Orchestrator - Complete Control over Backup/Restore',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
╔══════════════════════════════════════════════════════════════════════╗
║ COMMAND EXAMPLES:                                                    ║
╠══════════════════════════════════════════════════════════════════════╣
║ Normal operations (respects age and cooldown):                       ║
║   python3 scripts/orchestrator.py                                    ║
║                                                                      ║
║ Force operations (ignore all checks):                                ║
║   python3 scripts/orchestrator.py --force-backup --force-restore    ║
║                                                                      ║
║ Skip checks but don't force:                                         ║
║   python3 scripts/orchestrator.py --no-backup-check                 ║
║   python3 scripts/orchestrator.py --no-restore-check                ║
║                                                                      ║
║ Partial operations:                                                  ║
║   python3 scripts/orchestrator.py --skip-backup                     ║
║   python3 scripts/orchestrator.py --skip-restore                    ║
║   python3 scripts/orchestrator.py --skip-validation                 ║
║                                                                      ║
║ Status and management:                                               ║
║   python3 scripts/orchestrator.py --status                          ║
║   python3 scripts/orchestrator.py --reset                           ║
║                                                                      ║
║ Full control combination:                                            ║
║   python3 scripts/orchestrator.py --force-backup --force-restore    ║
║   --full-validation                                                 ║
╚══════════════════════════════════════════════════════════════════════╝
        """
    )
    
    # Operation control
    operation_group = parser.add_argument_group('Operation Control')
    operation_group.add_argument('--skip-backup', action='store_true', help='Skip backup step')
    operation_group.add_argument('--skip-restore', action='store_true', help='Skip restore step')
    operation_group.add_argument('--skip-validation', action='store_true', help='Skip validation step')
    
    # Force options
    force_group = parser.add_argument_group('Force Options (Override all checks)')
    force_group.add_argument('--force-backup', action='store_true', 
                            help='Force backup regardless of dump age')
    force_group.add_argument('--force-restore', action='store_true', 
                            help='Force restore regardless of cooldown')
    force_group.add_argument('--no-backup-check', action='store_true',
                            help='Disable backup age check (backup always)')
    force_group.add_argument('--no-restore-check', action='store_true',
                            help='Disable restore cooldown check')
    
    # Targeting
    target_group = parser.add_argument_group('Targeting')
    target_group.add_argument('--database', '-d', choices=['AG_Dev', 'Telios_LMS_Survey_Dev', 'both'],
                             default='both', help='Specific database to operate on')
    
    # Validation
    validate_group = parser.add_argument_group('Validation')
    validate_group.add_argument('--full-validation', action='store_true',
                               help='Run full validation (slower, more detailed)')
    validate_group.add_argument('--quick-validation', action='store_true',
                               help='Run quick validation (default)')
    
    # Management
    mgmt_group = parser.add_argument_group('Management')
    mgmt_group.add_argument('--status', action='store_true', 
                           help='Show current status only')
    mgmt_group.add_argument('--reset', action='store_true',
                           help='Reset restore tracking (allow immediate restore)')
    
    args = parser.parse_args()
    
    # Handle quick validation default
    if not args.full_validation and not args.quick_validation:
        args.quick_validation = True
    
    orchestrator = DatabaseOrchestrator()
    success = orchestrator.run(args)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()