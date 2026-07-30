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

missing=()
for key in JWT_SECRET SETTINGS_ENCRYPTION_KEY FRONTEND_URL CORS_ORIGINS; do
  if ! grep -E "^${key}=.+" .env >/dev/null 2>&1; then
    missing+=("$key")
  fi
done
if ((${#missing[@]} > 0)); then
  echo "ERROR: .env missing or empty: ${missing[*]}" >&2
  echo "Add them to $DEPLOY_DIR/.env (see deploy/env.example)." >&2
  exit 1
fi

if [[ -n "${GHCR_TOKEN:-}" ]]; then
  echo "${GHCR_TOKEN}" | docker login ghcr.io -u "${GHCR_USER:?GHCR_USER required with GHCR_TOKEN}" --password-stdin
fi

export IMAGE_TAG

compose() {
  docker compose --env-file .env -f "$COMPOSE_FILE" "$@"
}

echo "=== Pull images (tag=${IMAGE_TAG}) ==="
compose pull worker api-node web

echo "=== Ensure infra (postgres, redis) ==="
compose up -d postgres redis

echo "=== Apply migrations and restart worker ==="
compose up -d --force-recreate worker api-node

echo "=== Restart web (refresh nginx upstream after api-node recreate) ==="
compose up -d web
compose restart web

echo "=== Status ==="
compose ps

if [[ -x ./verify_prod_env.sh ]]; then
  COMPOSE_FILE="$COMPOSE_FILE" DEPLOY_DIR="$DEPLOY_DIR" ./verify_prod_env.sh
elif [[ -f ./scripts/verify_prod_env.sh ]]; then
  COMPOSE_FILE="$COMPOSE_FILE" DEPLOY_DIR="$DEPLOY_DIR" bash ./scripts/verify_prod_env.sh
fi

echo "Deploy complete: IMAGE_TAG=${IMAGE_TAG}"
