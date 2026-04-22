#!/bin/bash
# Simple wrapper to run the orchestrator

cd "$(dirname "$0")"
python3 scripts/orchestrator.py "$@"