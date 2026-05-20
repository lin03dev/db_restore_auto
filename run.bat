@echo off
REM Windows wrapper for the backup/restore/validation orchestrator.
cd /d "%~dp0"
set PYTHONUTF8=1

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found on PATH. Install Python 3.8+ or enable the Python launcher.
    exit /b 1
)

if "%~1"=="--help" (
    echo Usage: run.bat [OPTION]
    echo.
    echo Options:
    echo   no args        Normal run: backup, restore, validate
    echo   --force        Force backup and restore
    echo   --backup-only  Backup only
    echo   --restore-only Restore only
    echo   --status       Show backup and restore status
    echo   --reset        Reset restore tracking
    echo.
    echo Advanced options can be run with:
    echo   python scripts\orchestrator.py --help
    exit /b 0
)

if "%~1"=="--force" (
    python scripts\orchestrator.py --force-backup --force-restore
    exit /b %errorlevel%
)

if "%~1"=="--backup-only" (
    python scripts\orchestrator.py --skip-restore --skip-validation
    exit /b %errorlevel%
)

if "%~1"=="--restore-only" (
    python scripts\orchestrator.py --skip-backup
    exit /b %errorlevel%
)

python scripts\orchestrator.py %*
exit /b %errorlevel%
