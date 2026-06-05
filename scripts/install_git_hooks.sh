#!/usr/bin/env sh
# Устанавливает pre-commit hook для автообновления OpenAPI.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOK_SRC="$ROOT/.githooks/pre-commit"
HOOK_DST="$ROOT/.git/hooks/pre-commit"

if [ ! -d "$ROOT/.git" ]; then
  echo "Ошибка: .git не найден. Запустите из корня репозитория." >&2
  exit 1
fi

cp "$HOOK_SRC" "$HOOK_DST"
chmod +x "$HOOK_DST"
echo "Установлен hook: .git/hooks/pre-commit"
