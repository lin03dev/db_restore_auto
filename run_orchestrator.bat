@echo off
REM Windows wrapper to launch the orchestrator
cd /d "%~dp0"
set PYTHONUTF8=1
python scripts\orchestrator.py %*
