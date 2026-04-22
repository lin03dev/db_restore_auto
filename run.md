# Run complete pipeline (backup if needed, restore if allowed, validate)
./run.sh

# Force everything (ignore all checks)
./run.sh --force

# Backup only
./run.sh --backup-only

# Restore only
./run.sh --restore-only



==================================
# Backup specific database
python3 scripts/backup_single.py AG
python3 scripts/backup_single.py Telios

# Restore databases
python3 scripts/restore_script.py

# Force restore (ignore cooldown)
python3 scripts/restore_script.py --force

# Validate databases
python3 scripts/validate_restore.py --all

# Check status
python3 scripts/restore_script.py --status