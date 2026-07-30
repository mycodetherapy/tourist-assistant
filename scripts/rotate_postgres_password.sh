#!/usr/bin/env bash
# Смена пароля PostgreSQL на prod: ALTER USER + обновление .env + перезапуск worker/api-node.
# Запуск на VPS: cd /opt/tourist-assistant && bash scripts/rotate_postgres_password.sh
# Свой пароль: NEW_POSTGRES_PASSWORD='...' bash scripts/rotate_postgres_password.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=prod_compose_env.sh
source "$SCRIPT_DIR/prod_compose_env.sh"

cd "$PROD_DEPLOY_DIR"

if [[ ! -f "$PROD_ENV_FILE" ]]; then
  echo "ERROR: $PROD_ENV_FILE not found" >&2
  exit 1
fi

read_env() {
  grep -E "^${1}=" "$PROD_ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'"
}

is_weak_password() {
  local pass="$1"
  [[ -z "$pass" ]] && return 0
  [[ "$pass" == "tourist" ]] && return 0
  ((${#pass} < 16)) && return 0
  return 1
}

OLD_PASS="$(read_env POSTGRES_PASSWORD)"
NEW_PASS="${NEW_POSTGRES_PASSWORD:-}"

if [[ -z "$NEW_PASS" ]]; then
  NEW_PASS="$(openssl rand -hex 24)"
  echo "Сгенерирован новый пароль (сохраните в менеджере секретов):"
  echo "$NEW_PASS"
fi

if is_weak_password "$NEW_PASS"; then
  echo "ERROR: пароль слабый (минимум 16 символов, не «tourist»)." >&2
  exit 1
fi

if [[ "$NEW_PASS" == "$OLD_PASS" ]]; then
  echo "ERROR: новый пароль совпадает с текущим в .env" >&2
  exit 1
fi

if [[ -z "${IMAGE_TAG:-}" ]]; then
  echo "ERROR: IMAGE_TAG не задан (файл $PROD_TAG_FILE или export IMAGE_TAG=...)." >&2
  exit 1
fi

echo "=== Postgres up ==="
prod_compose up -d postgres
for _ in $(seq 1 30); do
  if prod_compose exec -T postgres pg_isready -U tourist -d tourist >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
prod_compose exec -T postgres pg_isready -U tourist -d tourist

SQL_PASS="${NEW_PASS//\'/\'\'}"
echo "=== ALTER USER tourist ==="
prod_compose exec -T postgres psql -U tourist -d tourist -v ON_ERROR_STOP=1 \
  -c "ALTER USER tourist WITH PASSWORD '${SQL_PASS}';"

echo "=== Обновление $PROD_ENV_FILE ==="
NEW_PASS="$NEW_PASS" PROD_ENV_FILE="$PROD_ENV_FILE" python3 - <<'PY'
import os
import re
from pathlib import Path

path = Path(os.environ["PROD_ENV_FILE"])
new_pass = os.environ["NEW_PASS"]
text = path.read_text(encoding="utf-8")
line = f"POSTGRES_PASSWORD={new_pass}"
if re.search(r"^POSTGRES_PASSWORD=", text, flags=re.M):
    text = re.sub(r"^POSTGRES_PASSWORD=.*$", line, text, flags=re.M)
else:
    text = text.rstrip() + "\n" + line + "\n"
path.write_text(text, encoding="utf-8")
path.chmod(0o600)
PY

echo "=== Перезапуск worker и api-node ==="
prod_compose up -d --force-recreate worker api-node

echo "Готово. Проверка:"
prod_compose exec -T api-node sh -c 'test -n "$DATABASE_URL" && echo "DATABASE_URL: OK"'
