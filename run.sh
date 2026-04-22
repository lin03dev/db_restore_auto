#!/bin/bash
# One command to rule them all

cd "$(dirname "$0")"

case "$1" in
    --force)
        echo "🚀 Running with force (ignoring age checks)..."
        python3 scripts/one_command.py --force-backup --force-restore
        ;;
    --backup-only)
        echo "📦 Backup only..."
        python3 scripts/one_command.py --skip-restore
        ;;
    --restore-only)
        echo "💾 Restore only..."
        python3 scripts/one_command.py --skip-backup
        ;;
    --help)
        echo "Usage: ./run.sh [OPTION]"
        echo ""
        echo "Options:"
        echo "  (no args)     - Normal run (backup if needed, restore if needed, validate)"
        echo "  --force       - Force backup and restore (ignore all checks)"
        echo "  --backup-only - Backup only"
        echo "  --restore-only- Restore only"
        echo "  --help        - Show this help"
        ;;
    *)
        echo "🚀 Running normal operation..."
        python3 scripts/one_command.py
        ;;
esac