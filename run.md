# First-time setup in the same activated environment, for example (py310)
python -m pip install -r requirements.txt

# Run complete pipeline (backup if needed, restore if allowed, validate)
# Windows PowerShell
.\run.bat

# Linux / WSL
./run.sh

# Force everything (ignore all checks)
# Windows PowerShell
.\run.bat --force
# Linux / WSL
./run.sh --force

# Backup only
# Windows PowerShell
.\run.bat --backup-only
# Linux / WSL
./run.sh --backup-only

# Restore only
# Windows PowerShell
.\run.bat --restore-only
# Linux / WSL
./run.sh --restore-only



==================================
# Backup specific database
python scripts/backup_single.py AG
python scripts/backup_single.py Telios

# Restore databases
python scripts/restore_script.py

# Force restore (ignore cooldown)
python scripts/restore_script.py --force

# Validate databases
python scripts/validate_restore.py --all

# Check status
python scripts/restore_script.py --status
