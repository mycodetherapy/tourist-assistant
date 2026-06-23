#!/usr/bin/env bash
# City pack: FO extract → extract.osm.pbf → poi.sqlite + OSRM.
# Использование: bash scripts/city_pack_prepare.sh kazan
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
SLUG="${1:-}"
if [[ -z "$SLUG" ]]; then
  echo "Использование: bash scripts/city_pack_prepare.sh <slug>" >&2
  exit 1
fi

eval "$("$PYTHON" - "$SLUG" <<'PY'
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from config.city_catalog import get_city_pack_spec, get_federal_district
from search.osm.nominatim import resolve_city_center

slug = sys.argv[1]
spec = get_city_pack_spec(slug)
if spec is None:
    raise SystemExit(f"unknown city pack slug: {slug}")
fo = get_federal_district(spec.federal_district)
if fo is None:
    raise SystemExit(f"unknown federal district: {spec.federal_district}")

center = resolve_city_center(spec.display_name)
if center is None:
    for name in spec.names:
        center = resolve_city_center(name)
        if center is not None:
            break
if center is None:
    raise SystemExit(f"Nominatim: не найден центр для {spec.display_name}")

def bbox_around(lon, lat, half_km):
    dlat = half_km / 111.0
    dlon = half_km / (111.0 * max(0.35, abs(math.cos(math.radians(lat)))))
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat

poi_bbox = bbox_around(center.lon, center.lat, spec.poi_radius_km)
route_bbox = bbox_around(center.lon, center.lat, spec.poi_radius_km + spec.routing_buffer_km)

spec.pack_dir.mkdir(parents=True, exist_ok=True)
spec.osrm_dir.mkdir(parents=True, exist_ok=True)

def emit(key, val):
    if isinstance(val, tuple):
        print(f"{key}='{','.join(str(x) for x in val)}'")
    else:
        print(f"{key}='{val}'")

emit("SLUG", slug)
emit("DISPLAY_NAME", spec.display_name)
emit("FEDERAL_DISTRICT", spec.federal_district)
emit("FO_PBF_NAME", fo.pbf_name)
emit("PACK_DIR", str(spec.pack_dir))
emit("OSRM_DIR", str(spec.osrm_dir))
emit("EXTRACT_PBF", str(spec.extract_pbf_path))
emit("POI_DB", str(spec.poi_db_path))
emit("OSRM_BASE", spec.osrm_base_name)
emit("COMPOSE_PROFILE", spec.compose_profile)
emit("POI_BBOX", poi_bbox)
emit("ROUTE_BBOX", route_bbox)
PY
)"

echo "=== City pack: $SLUG ($DISPLAY_NAME) ==="
bash "$ROOT/scripts/fo_ensure.sh" "$FEDERAL_DISTRICT"
export SLUG DISPLAY_NAME FEDERAL_DISTRICT PACK_DIR OSRM_DIR EXTRACT_PBF POI_DB OSRM_BASE POI_BBOX ROUTE_BBOX FO_PBF_NAME
bash "$ROOT/scripts/city_pack_prepare_core.sh"

"$PYTHON" - "$SLUG" "$PACK_DIR/meta.json" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from config.city_catalog import get_city_pack_spec
from search.osm.nominatim import resolve_city_center

slug, meta_path = sys.argv[1], Path(sys.argv[2])
spec = get_city_pack_spec(slug)
center = resolve_city_center(spec.display_name)
if center is None:
    for name in spec.names:
        center = resolve_city_center(name)
        if center is not None:
            break
meta = {
    "slug": slug,
    "display_name": spec.display_name,
    "federal_district": spec.federal_district,
    "prepared_at": datetime.now(timezone.utc).isoformat(),
    "center": {"lon": center.lon, "lat": center.lat},
    "poi_radius_km": spec.poi_radius_km,
    "routing_buffer_km": spec.routing_buffer_km,
    "compose_profile": spec.compose_profile,
    "osrm_service": spec.osrm_service,
    "lazy": False,
}
meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
PY

echo ""
echo "Готово: $PACK_DIR"
echo "Запуск OSRM: docker compose --profile routing --profile $COMPOSE_PROFILE up -d"
