#!/usr/bin/env bash
# Nightly Postgres backup for VPS (cron).
# Example crontab: 0 3 * * * /opt/tourist-assistant/scripts/pg_backup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${PG_BACKUP_DIR:-$ROOT/backups/postgres}"
RETENTION_DAYS="${PG_BACKUP_RETENTION_DAYS:-14}"
STAMP="$(date +%Y-%m-%d_%H%M%S)"
FILE="$BACKUP_DIR/tourist_${STAMP}.dump"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is not set" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
pg_dump "$DATABASE_URL" -Fc -f "$FILE"
find "$BACKUP_DIR" -name 'tourist_*.dump' -mtime +"$RETENTION_DAYS" -delete
echo "Backup written: $FILE"
