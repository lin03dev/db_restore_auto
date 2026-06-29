#!/bin/sh
set -eu

mkdir -p /app/state /app/dumps /app/logs/backup /app/logs/restore /app/logs/error /app/logs/reports

if [ -d /app/.restore_tracking.json ]; then
  echo "ERROR: /app/.restore_tracking.json is a directory." >&2
  echo "Remove it on the host and recreate: echo '{}' > backend/.restore_tracking.json" >&2
  exit 1
fi

if [ ! -f /app/state/.restore_tracking.json ]; then
  printf '%s\n' '{}' > /app/state/.restore_tracking.json
fi

ln -sf /app/state/.restore_tracking.json /app/.restore_tracking.json

exec "$@"
