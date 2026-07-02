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

OSMIUM_IMAGE="${OSMIUM_IMAGE:-local-osmium-tool}"
DOCKER_PLATFORM="${DOCKER_PLATFORM:-}"

if ! docker image inspect "$OSMIUM_IMAGE" >/dev/null 2>&1; then
  echo "Сборка локального образа osmium-tool (scripts/Dockerfile.osmium) …"
  docker build -t local-osmium-tool -f "$ROOT/scripts/Dockerfile.osmium" "$ROOT/scripts"
fi

IFS=',' read -r POI_W POI_S POI_E POI_N <<< "$POI_BBOX"
IFS=',' read -r ROUTE_W ROUTE_S ROUTE_E ROUTE_N <<< "$ROUTE_BBOX"

if [[ ! -f "$EXTRACT_PBF" ]] || [[ "${FORCE_EXTRACT:-}" == "1" ]]; then
  echo "osmium extract …"
  docker run --rm \
    ${DOCKER_PLATFORM:+--platform "$DOCKER_PLATFORM"} \
    -v "$ROOT/data/fo:/fo:ro" \
    -v "$PACK_DIR:/out" \
    "$OSMIUM_IMAGE" \
    extract -b "$ROUTE_W,$ROUTE_S,$ROUTE_E,$ROUTE_N" "/fo/$FO_PBF_NAME" -o "/out/extract.osm.pbf" --overwrite
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
