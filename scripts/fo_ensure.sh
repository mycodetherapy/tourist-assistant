#!/usr/bin/env bash
# Скачивание PBF федерального округа Geofabrik в data/fo/.
# Использование: bash scripts/fo_ensure.sh volga
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FO_ID="${1:-volga}"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
DATA_DIR="${TOURIST_DATA_DIR:-$ROOT/data}/fo"
CATALOG="${FEDERAL_DISTRICTS_YAML:-$ROOT/config/federal_districts.yaml}"

if [[ ! -f "$CATALOG" ]]; then
  echo "Нет $CATALOG" >&2
  exit 1
fi

read -r PBF_URL PBF_NAME MIN_BYTES < <(
  "$PYTHON" - "$FO_ID" "$CATALOG" <<'PY'
import sys
import yaml
fo_id, path = sys.argv[1], sys.argv[2]
raw = yaml.safe_load(open(path, encoding="utf-8"))
item = (raw.get("districts") or {}).get(fo_id)
if not item:
    raise SystemExit(f"unknown federal district: {fo_id}")
print(item["geofabrik_url"], item["pbf_name"], int(item.get("min_pbf_bytes", 50 * 1024 * 1024)))
PY
)

PBF="$DATA_DIR/$PBF_NAME"
mkdir -p "$DATA_DIR"

# Миграция: старый путь data/osrm/*.pbf
LEGACY="$ROOT/data/osrm/$PBF_NAME"
if [[ ! -f "$PBF" ]] && [[ -f "$LEGACY" ]]; then
  echo "Копирую FO PBF из $LEGACY"
  cp "$LEGACY" "$PBF"
fi

is_valid_pbf() {
  local file="$1"
  [[ -f "$file" ]] || return 1
  local size
  size="$(wc -c <"$file" | tr -d ' ')"
  [[ "$size" -ge "$MIN_BYTES" ]] || return 1
  local head_bytes
  # Binary PBF: avoid bash $() null-byte warnings
  head_bytes="$(head -c 16 "$file" 2>/dev/null | tr -d '\0' || true)"
  [[ "$head_bytes" != "<!DOCTYPE html>"* ]] || return 1
  [[ "$head_bytes" != "<html"* ]] || return 1
  return 0
}

download_to() {
  local dest="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -L --fail --retry 3 --retry-delay 5 -o "$dest" "$PBF_URL"
  elif command -v wget >/dev/null 2>&1; then
    wget --tries=3 -O "$dest" "$PBF_URL"
  else
    echo "curl/wget нет — скачиваю через python" >&2
    "$PYTHON" - "$PBF_URL" "$dest" <<'PY'
import sys
import urllib.request

url, dest = sys.argv[1], sys.argv[2]
urllib.request.urlretrieve(url, dest)
PY
  fi
}

if [[ "${FORCE_DOWNLOAD:-}" == "1" ]] || ! is_valid_pbf "$PBF"; then
  TMP="$PBF.partial"
  rm -f "$TMP"
  echo "Скачивание $PBF_URL …"
  if ! download_to "$TMP"; then
    rm -f "$TMP"
    echo "Ошибка скачивания FO (старый файл не тронут, если был)" >&2
    exit 1
  fi
  if ! is_valid_pbf "$TMP"; then
    rm -f "$TMP"
    echo "Ошибка: скачанный файл не похож на .osm.pbf (старый файл не тронут, если был)" >&2
    exit 1
  fi
  mv -f "$TMP" "$PBF"
fi

if ! is_valid_pbf "$PBF"; then
  echo "Ошибка: файл не похож на .osm.pbf" >&2
  exit 1
fi

echo "FO готов: $PBF ($(du -h "$PBF" | cut -f1))"
