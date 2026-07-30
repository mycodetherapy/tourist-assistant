#!/usr/bin/env bash
# Миграция данных tourist-assistant_* → progulyai_* (Postgres + Redis).
# Запуск на VPS: cd /opt/tourist-assistant && bash migrate_legacy_volumes.sh
set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/tourist-assistant}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
OLD_PG="${OLD_PG_VOLUME:-tourist-assistant_pg_data}"
OLD_REDIS="${OLD_REDIS_VOLUME:-tourist-assistant_redis_data}"
NEW_PG="${NEW_PG_VOLUME:-progulyai_pg_data}"
NEW_REDIS="${NEW_REDIS_VOLUME:-progulyai_redis_data}"

cd "$DEPLOY_DIR"

if [[ ! -f .env ]]; then
  echo "ERROR: .env not found in $DEPLOY_DIR" >&2
  exit 1
fi

if [[ -f .deploy-image-tag ]]; then
  export IMAGE_TAG="$(tr -d '[:space:]' < .deploy-image-tag)"
fi
if [[ -z "${IMAGE_TAG:-}" ]]; then
  echo "ERROR: set IMAGE_TAG or create .deploy-image-tag" >&2
  exit 1
fi

compose() {
  docker compose --env-file .env -f "$COMPOSE_FILE" "$@"
}

volume_exists() {
  docker volume inspect "$1" >/dev/null 2>&1
}

copy_volume() {
  local from="$1"
  local to="$2"
  echo "=== Copy $from → $to ==="
  docker run --rm \
    -v "${from}:/from:ro" \
    -v "${to}:/to" \
    alpine:3.20 \
    sh -c 'cd /from && cp -a . /to'
}

for vol in "$OLD_PG" "$OLD_REDIS" "$NEW_PG" "$NEW_REDIS"; do
  if ! volume_exists "$vol"; then
    echo "ERROR: volume missing: $vol" >&2
    docker volume ls | grep -E 'pg_data|redis' || true
    exit 1
  fi
done

echo "=== Stop progulyai stack (postgres + redis must be offline) ==="
compose stop postgres redis worker api-node web 2>/dev/null || compose down

echo ""
echo "=== Backup counts (old postgres) ==="
docker run --rm -d --name ta_migrate_pg_old \
  -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-tourist}" \
  -v "${OLD_PG}:/var/lib/postgresql/data" \
  postgres:16-alpine >/dev/null
for i in $(seq 1 30); do
  if docker exec ta_migrate_pg_old pg_isready -U tourist -d tourist >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker exec ta_migrate_pg_old psql -U tourist -d tourist -c \
  "SELECT 'users' AS tbl, count(*) FROM users UNION ALL SELECT 'trips', count(*) FROM trips;" || true
docker rm -f ta_migrate_pg_old >/dev/null

echo ""
read -r -p "Перезаписать $NEW_PG и $NEW_REDIS данными из $OLD_PG / $OLD_REDIS? [y/N] " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
  echo "Отменено."
  exit 0
fi

echo "=== Wipe target volumes ==="
docker run --rm -v "${NEW_PG}:/data" alpine:3.20 sh -c 'rm -rf /data/*'
docker run --rm -v "${NEW_REDIS}:/data" alpine:3.20 sh -c 'rm -rf /data/*'

copy_volume "$OLD_PG" "$NEW_PG"
copy_volume "$OLD_REDIS" "$NEW_REDIS"

echo ""
echo "=== Start stack ==="
compose up -d postgres redis
for i in $(seq 1 30); do
  if compose exec -T postgres pg_isready -U tourist -d tourist >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
compose up -d worker api-node web

echo ""
echo "=== Verify (new postgres) ==="
compose exec -T postgres psql -U tourist -d tourist -c \
  "SELECT 'users' AS tbl, count(*) FROM users UNION ALL SELECT 'trips', count(*) FROM trips;"

echo ""
read -r -p "Данные на месте? Удалить старые volumes $OLD_PG и $OLD_REDIS? [y/N] " drop_confirm
if [[ "$drop_confirm" == "y" || "$drop_confirm" == "Y" ]]; then
  docker volume rm "$OLD_PG" "$OLD_REDIS"
  echo "Старые volumes удалены."
else
  echo "Старые volumes сохранены: $OLD_PG $OLD_REDIS"
fi

echo "Миграция завершена."
