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
for key in JWT_SECRET SETTINGS_ENCRYPTION_KEY FRONTEND_URL CORS_ORIGINS POSTGRES_PASSWORD; do
  if ! grep -E "^${key}=.+" .env >/dev/null 2>&1; then
    missing+=("$key")
  fi
done
if ((${#missing[@]} > 0)); then
  echo "ERROR: .env missing or empty: ${missing[*]}" >&2
  echo "Add them to $DEPLOY_DIR/.env (see deploy/env.example)." >&2
  exit 1
fi

if [[ -z "${GHCR_TOKEN:-}" ]]; then
  echo "ERROR: GHCR_TOKEN is not set." >&2
  echo "In GitHub Actions set secrets GHCR_USER and GHCR_READ_TOKEN (PAT with read:packages)." >&2
  echo "Or on VPS: export GHCR_USER=... GHCR_TOKEN=... before ./deploy_prod.sh" >&2
  exit 1
fi
if [[ -z "${GHCR_USER:-}" ]]; then
  echo "ERROR: GHCR_USER is required when GHCR_TOKEN is set." >&2
  exit 1
fi

echo "=== Docker login ghcr.io (user=${GHCR_USER}) ==="
if ! echo "${GHCR_TOKEN}" | docker login ghcr.io -u "${GHCR_USER}" --password-stdin; then
  echo "ERROR: docker login ghcr.io failed. Check GHCR_USER / GHCR_READ_TOKEN (read:packages)." >&2
  exit 1
fi

export IMAGE_TAG
echo "$IMAGE_TAG" > .deploy-image-tag

compose() {
  docker compose --env-file .env -f "$COMPOSE_FILE" "$@"
}

stop_legacy_web() {
  echo "=== Retire legacy stack on :5173 (docker-compose.yml) ==="
  if [[ -f docker-compose.yml ]]; then
    docker compose -f docker-compose.yml --profile docker-web down --remove-orphans 2>/dev/null || true
  fi
  local cid
  for cid in $(docker ps -q --filter "publish=5173" 2>/dev/null); do
    echo "Stopping container on host :5173: $cid"
    docker rm -f "$cid" 2>/dev/null || true
  done
}

echo "=== Pull images (tag=${IMAGE_TAG}) ==="
compose pull worker api-node web

echo "=== Ensure infra (postgres, redis) ==="
compose up -d postgres redis

echo "=== Apply migrations and restart worker ==="
compose up -d --force-recreate worker api-node

echo "=== Restart web (refresh nginx upstream after api-node recreate) ==="
stop_legacy_web
compose up -d --force-recreate web
compose restart web

echo "=== Status ==="
compose ps

if [[ -x ./verify_prod_env.sh ]]; then
  COMPOSE_FILE="$COMPOSE_FILE" DEPLOY_DIR="$DEPLOY_DIR" ./verify_prod_env.sh
elif [[ -f ./scripts/verify_prod_env.sh ]]; then
  COMPOSE_FILE="$COMPOSE_FILE" DEPLOY_DIR="$DEPLOY_DIR" bash ./scripts/verify_prod_env.sh
fi

echo "Deploy complete: IMAGE_TAG=${IMAGE_TAG}"
