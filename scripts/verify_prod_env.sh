#!/usr/bin/env bash
# Проверка обязательных переменных prod (.env + контейнер api-node).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -n "${DEPLOY_DIR:-}" ]]; then
  ROOT="$DEPLOY_DIR"
elif [[ -f "$SCRIPT_DIR/../docker-compose.prod.yml" ]]; then
  ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
elif [[ -f "$SCRIPT_DIR/docker-compose.prod.yml" ]]; then
  ROOT="$SCRIPT_DIR"
else
  ROOT="$SCRIPT_DIR"
fi

cd "$ROOT"
# shellcheck source=prod_compose_env.sh
source "$SCRIPT_DIR/prod_compose_env.sh"

echo "=== prod compose ==="
echo "dir=$PROD_DEPLOY_DIR file=$PROD_COMPOSE_FILE IMAGE_TAG=${IMAGE_TAG:-MISSING}"

echo ""
echo "=== .env на хосте (только имена, длина значения) ==="
for key in JWT_SECRET SETTINGS_ENCRYPTION_KEY FRONTEND_URL CORS_ORIGINS YANDEX_MAPS_API_KEY POSTGRES_PASSWORD GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET; do
  line=$(grep -E "^${key}=" .env 2>/dev/null | head -1 || true)
  if [[ -z "$line" ]]; then
    echo "$key: MISSING in .env"
  else
    val="${line#*=}"
    echo "$key: len=${#val}"
  fi
done

if [[ -f "$PROD_TAG_FILE" ]]; then
  echo "deploy-image-tag: $(tr -d '[:space:]' < "$PROD_TAG_FILE")"
else
  echo "deploy-image-tag: MISSING ($PROD_TAG_FILE)"
fi

echo ""
echo "=== api-node container ==="
if [[ -z "${IMAGE_TAG:-}" ]]; then
  echo "IMAGE_TAG не задан — задайте export IMAGE_TAG=latest или дождитесь deploy (файл .deploy-image-tag)."
elif prod_compose ps api-node 2>/dev/null | grep -q Up; then
  prod_compose exec -T api-node sh -c '
    test -n "$JWT_SECRET" && echo "JWT_SECRET: OK (len=${#JWT_SECRET})" || echo "JWT_SECRET: MISSING"
    test -n "$SETTINGS_ENCRYPTION_KEY" && echo "SETTINGS_ENCRYPTION_KEY: OK (len=${#SETTINGS_ENCRYPTION_KEY})" || echo "SETTINGS_ENCRYPTION_KEY: MISSING"
  '
else
  echo "api-node не запущен — выполните: bash prod_ps.sh или IMAGE_TAG=latest prod_compose up -d api-node"
fi
