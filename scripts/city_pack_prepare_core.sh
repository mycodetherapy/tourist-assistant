#!/usr/bin/env bash
# Общие шаги prepare (env: SLUG, PACK_DIR, ROUTE_BBOX, POI_BBOX, …).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

: "${SLUG:?}"
: "${PACK_DIR:?}"
: "${EXTRACT_PBF:?}"
: "${POI_DB:?}"
: "${FO_PBF_NAME:?}"
: "${DISPLAY_NAME:?}"
: "${ROUTE_BBOX:?}"
: "${POI_BBOX:?}"

# В контейнере worker: TOURIST_DATA_DIR=/app/data (файлы),
# TOURIST_HOST_DATA_DIR=<host>/data (для docker run -v через docker.sock).
DATA_DIR="${TOURIST_DATA_DIR:-$ROOT/data}"
HOST_DATA_DIR="${TOURIST_HOST_DATA_DIR:-$DATA_DIR}"

OSMIUM_IMAGE="${OSMIUM_IMAGE:-local-osmium-tool}"
DOCKER_PLATFORM="${DOCKER_PLATFORM:-}"
# complete_ways жрёт RAM на FO ~700MB+; на VPS 4 ГБ — simple (+ swap).
OSMIUM_EXTRACT_STRATEGY="${OSMIUM_EXTRACT_STRATEGY:-simple}"
OSMIUM_DOCKER_MEMORY="${OSMIUM_DOCKER_MEMORY:-1536m}"
OSMIUM_DOCKER_MEMORY_SWAP="${OSMIUM_DOCKER_MEMORY_SWAP:-6g}"

IFS=',' read -r POI_W POI_S POI_E POI_N <<< "$POI_BBOX"
IFS=',' read -r ROUTE_W ROUTE_S ROUTE_E ROUTE_N <<< "$ROUTE_BBOX"

pbf_usable() {
  "$PYTHON" "$ROOT/search/osm/pbf_usable.py" "$1"
}

run_osmium_extract() {
  local src="$1"
  local dest="$2"
  mkdir -p "$PACK_DIR"
  rm -f "$dest"
  if command -v osmium >/dev/null 2>&1; then
    echo "osmium extract (native, strategy=$OSMIUM_EXTRACT_STRATEGY) …"
    osmium extract \
      --strategy "$OSMIUM_EXTRACT_STRATEGY" \
      -b "$ROUTE_W,$ROUTE_S,$ROUTE_E,$ROUTE_N" \
      "$src" \
      -o "$dest" \
      --overwrite
    return
  fi
  if ! docker image inspect "$OSMIUM_IMAGE" >/dev/null 2>&1; then
    echo "Сборка локального образа osmium-tool (scripts/Dockerfile.osmium) …"
    docker build -t local-osmium-tool -f "$ROOT/scripts/Dockerfile.osmium" "$ROOT/scripts"
  fi
  echo "osmium extract (docker, strategy=$OSMIUM_EXTRACT_STRATEGY, memory=$OSMIUM_DOCKER_MEMORY swap=$OSMIUM_DOCKER_MEMORY_SWAP) …"
  docker run --rm \
    ${DOCKER_PLATFORM:+--platform "$DOCKER_PLATFORM"} \
    --memory "$OSMIUM_DOCKER_MEMORY" \
    --memory-swap "$OSMIUM_DOCKER_MEMORY_SWAP" \
    -v "$HOST_DATA_DIR/fo:/fo:ro" \
    -v "$HOST_DATA_DIR/cities/$SLUG:/out" \
    "$OSMIUM_IMAGE" \
    extract \
    --strategy "$OSMIUM_EXTRACT_STRATEGY" \
    -b "$ROUTE_W,$ROUTE_S,$ROUTE_E,$ROUTE_N" \
    "/fo/$FO_PBF_NAME" \
    -o "/out/$(basename "$dest")" \
    --overwrite
}

FO_SRC="$DATA_DIR/fo/$FO_PBF_NAME"
PARTIAL="$PACK_DIR/extract.osm.pbf.partial"

if ! pbf_usable "$EXTRACT_PBF" || [[ "${FORCE_EXTRACT:-}" == "1" ]]; then
  echo "osmium extract (strategy=$OSMIUM_EXTRACT_STRATEGY) …"
  rm -f "$PARTIAL" "$EXTRACT_PBF"
  run_osmium_extract "$FO_SRC" "$PARTIAL"
  if ! pbf_usable "$PARTIAL"; then
    echo "osmium extract дал пустой или битый PBF — не хватило памяти или bbox пуст" >&2
    rm -f "$PARTIAL"
    exit 1
  fi
  mv -f "$PARTIAL" "$EXTRACT_PBF"
fi

if [[ ! -f "$POI_DB" ]] || [[ "${FORCE_POI:-}" == "1" ]]; then
  "$PYTHON" "$ROOT/scripts/build_poi_index.py" \
    "$EXTRACT_PBF" "$POI_DB" \
    --west "$POI_W" --south "$POI_S" --east "$POI_E" --north "$POI_N" \
    --city-hint "$DISPLAY_NAME"
fi

"$PYTHON" - "$SLUG" "$PACK_DIR/meta.json" "$DISPLAY_NAME" "${FEDERAL_DISTRICT:-volga}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

slug, meta_path, display_name, fo = sys.argv[1], Path(sys.argv[2]), sys.argv[3], sys.argv[4]
meta = {
    "slug": slug,
    "display_name": display_name,
    "federal_district": fo,
    "prepared_at": datetime.now(timezone.utc).isoformat(),
    "lazy": True,
}
meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
PY

echo "pack готов: $PACK_DIR"
