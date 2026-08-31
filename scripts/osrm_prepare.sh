#!/usr/bin/env bash
# Сборка пешего OSRM-графа из city extract (MLD).
# Использование: bash scripts/osrm_prepare.sh kazan
#
# Требует: Docker, data/cities/<slug>/extract.osm.pbf
# Результат: data/cities/<slug>/osrm/<slug>.osrm*
#
# В Docker-worker задайте TOURIST_HOST_DATA_DIR=<абсолютный путь хоста к data>
# для bind mount через docker.sock (на Mac /app/data не шарится).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SLUG="${1:-}"
OSRM_IMAGE="${OSRM_IMAGE:-ghcr.io/project-osrm/osrm-backend:v5.27.1}"
PROFILE_LUA="${OSRM_PROFILE_LUA:-/opt/foot.lua}"

if [[ -z "$SLUG" ]]; then
  echo "Usage: bash scripts/osrm_prepare.sh <city-slug>" >&2
  echo "Example: bash scripts/osrm_prepare.sh kazan" >&2
  exit 1
fi

DATA_DIR="${TOURIST_DATA_DIR:-$ROOT/data}"
HOST_DATA_DIR="${TOURIST_HOST_DATA_DIR:-$DATA_DIR}"

CITY_DIR="$DATA_DIR/cities/$SLUG"
EXTRACT="$CITY_DIR/extract.osm.pbf"
OUT_DIR="$CITY_DIR/osrm"
HOST_OUT_DIR="$HOST_DATA_DIR/cities/$SLUG/osrm"

if [[ ! -f "$EXTRACT" ]]; then
  echo "Нет $EXTRACT — сначала соберите city pack (scripts/city_pack_prepare.sh $SLUG)" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"
# OSRM пишет рядом с .osm.pbf; копируем extract во временное имя в out/
WORK_PBF="$OUT_DIR/${SLUG}.osm.pbf"
cp -f "$EXTRACT" "$WORK_PBF"

echo "OSRM extract (foot) → $OUT_DIR …"
docker run --rm -t \
  -v "$HOST_OUT_DIR:/data" \
  "$OSRM_IMAGE" \
  osrm-extract -p "$PROFILE_LUA" "/data/${SLUG}.osm.pbf"

echo "OSRM partition …"
docker run --rm -t \
  -v "$HOST_OUT_DIR:/data" \
  "$OSRM_IMAGE" \
  osrm-partition "/data/${SLUG}.osrm"

echo "OSRM customize …"
docker run --rm -t \
  -v "$HOST_OUT_DIR:/data" \
  "$OSRM_IMAGE" \
  osrm-customize "/data/${SLUG}.osrm"

# Исходный pbf в out/ больше не нужен для routed
rm -f "$WORK_PBF"

echo "Готово: $OUT_DIR/${SLUG}.osrm* ($(du -sh "$OUT_DIR" | cut -f1))"
echo "Запуск: OSRM_DATASET=$SLUG docker compose --profile osrm up -d osrm"
