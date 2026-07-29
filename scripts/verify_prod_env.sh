#!/usr/bin/env bash
# Проверка обязательных переменных prod (.env + контейнер api-node).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== .env на хосте (только имена, длина значения) ==="
for key in JWT_SECRET SETTINGS_ENCRYPTION_KEY FRONTEND_URL CORS_ORIGINS YANDEX_MAPS_API_KEY; do
  line=$(grep -E "^${key}=" .env 2>/dev/null | head -1 || true)
  if [[ -z "$line" ]]; then
    echo "$key: MISSING in .env"
  else
    val="${line#*=}"
    echo "$key: len=${#val}"
  fi
done

echo ""
echo "=== docker compose config (required vars) ==="
docker compose config 2>&1 | grep -E "JWT_SECRET|SETTINGS_ENCRYPTION" | sed 's/=.*/=***/' || true

echo ""
echo "=== api-node container ==="
if docker compose ps api-node 2>/dev/null | grep -q Up; then
  docker compose exec -T api-node sh -c '
    test -n "$JWT_SECRET" && echo "JWT_SECRET: OK (len=${#JWT_SECRET})" || echo "JWT_SECRET: MISSING"
    test -n "$SETTINGS_ENCRYPTION_KEY" && echo "SETTINGS_ENCRYPTION_KEY: OK (len=${#SETTINGS_ENCRYPTION_KEY})" || echo "SETTINGS_ENCRYPTION_KEY: MISSING"
  '
else
  echo "api-node не запущен — выполните: docker compose up -d api-node"
fi
