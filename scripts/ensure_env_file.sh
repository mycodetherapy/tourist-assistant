#!/usr/bin/env bash
# Создаёт .env из шаблона только если файла ещё нет (не затирает ключи).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -f .env ]]; then
  echo ".env уже есть — не перезаписываю (ключи сохранены)."
  exit 0
fi
cp .env.example .env
echo "Создан .env из .env.example — заполните LLM_API_KEY и др."
