#!/usr/bin/env bash
# Pull готовых образов из GHCR и перезапуск prod-стека (без git pull / build).
set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/tourist-assistant}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
IMAGE_TAG="${IMAGE_TAG:?IMAGE_TAG is required}"

cd "$DEPLOY_DIR"

if [[ ! -f .env ]]; then
  echo "ERROR: $DEPLOY_DIR/.env not found. Copy deploy/env.example and fill secrets." >&2
  exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "ERROR: $DEPLOY_DIR/$COMPOSE_FILE not found." >&2
  exit 1
fi

if [[ -n "${GHCR_TOKEN:-}" ]]; then
  echo "${GHCR_TOKEN}" | docker login ghcr.io -u "${GHCR_USER:?GHCR_USER required with GHCR_TOKEN}" --password-stdin
fi

export IMAGE_TAG

echo "=== Pull images (tag=${IMAGE_TAG}) ==="
docker compose -f "$COMPOSE_FILE" pull worker api-node web

echo "=== Ensure infra (postgres, redis) ==="
docker compose -f "$COMPOSE_FILE" up -d postgres redis

echo "=== Apply migrations and restart worker ==="
docker compose -f "$COMPOSE_FILE" up -d --force-recreate worker api-node

echo "=== Restart web (refresh nginx upstream after api-node recreate) ==="
docker compose -f "$COMPOSE_FILE" up -d web
docker compose -f "$COMPOSE_FILE" restart web

echo "=== Status ==="
docker compose -f "$COMPOSE_FILE" ps

if [[ -x ./verify_prod_env.sh ]]; then
  COMPOSE_FILE="$COMPOSE_FILE" DEPLOY_DIR="$DEPLOY_DIR" ./verify_prod_env.sh
elif [[ -f ./scripts/verify_prod_env.sh ]]; then
  COMPOSE_FILE="$COMPOSE_FILE" DEPLOY_DIR="$DEPLOY_DIR" bash ./scripts/verify_prod_env.sh
fi

echo "Deploy complete: IMAGE_TAG=${IMAGE_TAG}"
