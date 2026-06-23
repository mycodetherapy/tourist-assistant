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
: "${OSRM_DIR:?}"
: "${OSRM_BASE:?}"
: "${FO_PBF_NAME:?}"
: "${DISPLAY_NAME:?}"
: "${ROUTE_BBOX:?}"
: "${POI_BBOX:?}"

OSMIUM_IMAGE="${OSMIUM_IMAGE:-local-osmium-tool}"
if ! docker image inspect "$OSMIUM_IMAGE" >/dev/null 2>&1; then
  echo "Сборка локального образа osmium-tool (scripts/Dockerfile.osmium) …"
  docker build -t local-osmium-tool -f "$ROOT/scripts/Dockerfile.osmium" "$ROOT/scripts"
fi
OSRM_IMAGE="${OSRM_IMAGE:-ghcr.io/project-osrm/osrm-backend:latest}"
PROFILE="${OSRM_PROFILE:-foot}"
DOCKER_PLATFORM="${DOCKER_PLATFORM:-}"
DOCKER_MEMORY="${DOCKER_MEMORY:-}"

IFS=',' read -r POI_W POI_S POI_E POI_N <<< "$POI_BBOX"
IFS=',' read -r ROUTE_W ROUTE_S ROUTE_E ROUTE_N <<< "$ROUTE_BBOX"

docker_osrm() {
  local mount="$1"
  shift
  local -a args=(run --rm -v "$mount:/data")
  if [[ -n "$DOCKER_MEMORY" ]]; then
    args+=(--memory="$DOCKER_MEMORY")
  fi
  if [[ -n "$DOCKER_PLATFORM" ]]; then
    args+=(--platform "$DOCKER_PLATFORM")
  fi
  docker "${args[@]}" "$OSRM_IMAGE" "$@"
}

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

if [[ ! -f "$OSRM_DIR/${OSRM_BASE}.osrm.mldgr" ]] || [[ "${FORCE_REBUILD:-}" == "1" ]]; then
  if [[ ! -f "$OSRM_DIR/${OSRM_BASE}.osrm.edges" ]] || [[ "${FORCE_REBUILD:-}" == "1" ]]; then
    rm -f "$PACK_DIR"/extract.osrm* "$OSRM_DIR"/"${OSRM_BASE}.osrm"*
    docker_osrm "$PACK_DIR" osrm-extract -p "/opt/${PROFILE}.lua" "/data/extract.osm.pbf"
    for f in "$PACK_DIR"/extract.osrm*; do
      [[ -e "$f" ]] || continue
      base="$(basename "$f")"
      mv -f "$f" "$OSRM_DIR/${OSRM_BASE}.${base#extract.}"
    done
  fi
  if [[ ! -f "$OSRM_DIR/${OSRM_BASE}.osrm.partition" ]] || [[ "${FORCE_REBUILD:-}" == "1" ]]; then
    docker_osrm "$OSRM_DIR" osrm-partition "/data/${OSRM_BASE}.osrm"
  fi
  docker_osrm "$OSRM_DIR" osrm-customize "/data/${OSRM_BASE}.osrm"
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
    "compose_profile": f"routing-city-{slug}",
    "osrm_service": f"osrm-{slug}",
}
meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
PY

echo "pack готов: $PACK_DIR"
