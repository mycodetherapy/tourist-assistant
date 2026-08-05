#!/usr/bin/env bash
# Удаление истёкших guest-пользователей и их прогулок (cron на VPS).
#
# Пример crontab (ежедневно в 04:15 UTC):
#   15 4 * * * /opt/tourist-assistant/scripts/guest_cleanup_cron.sh >> /var/log/progulyai-guest-cleanup.log 2>&1
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT/deploy/docker-compose.prod.yml}"

if [[ -f "$COMPOSE_FILE" ]]; then
  docker compose -f "$COMPOSE_FILE" exec -T api-node node dist/cli/guestCleanup.js
else
  cd "$ROOT/api-node"
  npm run guest:cleanup
fi
