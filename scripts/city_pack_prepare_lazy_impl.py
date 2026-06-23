#!/usr/bin/env python3
"""Lazy city pack для города вне config/city_packs.yaml."""

from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.city_catalog import fo_data_dir, get_federal_district
from search.osm.nominatim import resolve_city_center


def _bbox_around(lon: float, lat: float, half_km: float) -> tuple[float, float, float, float]:
    dlat = half_km / 111.0
    dlon = half_km / (111.0 * max(0.35, abs(math.cos(math.radians(lat)))))
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat


def main() -> int:
    if len(sys.argv) < 4:
        print("usage: city_pack_prepare_lazy_impl.py <slug> <city> <federal_district>", file=sys.stderr)
        return 1
    slug, city, fo_id = sys.argv[1], sys.argv[2], sys.argv[3]
    center = resolve_city_center(city)
    if center is None:
        print(f"Nominatim: не найден {city}", file=sys.stderr)
        return 1
    fo = get_federal_district(fo_id)
    if fo is None:
        print(f"unknown FO: {fo_id}", file=sys.stderr)
        return 1

    poi_r, buf = 4.5, 1.0
    poi_bbox = _bbox_around(center.lon, center.lat, poi_r)
    route_bbox = _bbox_around(center.lon, center.lat, poi_r + buf)

    pack_dir = ROOT / "data" / "cities" / slug
    pack_dir.mkdir(parents=True, exist_ok=True)
    osrm_dir = pack_dir / "osrm"
    osrm_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(["bash", str(ROOT / "scripts" / "fo_ensure.sh"), fo_id], check=True, cwd=str(ROOT))

    import os

    env = {
        **os.environ,
        "SLUG": slug,
        "DISPLAY_NAME": city,
        "FEDERAL_DISTRICT": fo_id,
        "FO_PBF_NAME": fo.pbf_name,
        "PACK_DIR": str(pack_dir),
        "OSRM_DIR": str(osrm_dir),
        "EXTRACT_PBF": str(pack_dir / "extract.osm.pbf"),
        "POI_DB": str(pack_dir / "poi.sqlite"),
        "OSRM_BASE": slug,
        "POI_BBOX": ",".join(str(x) for x in poi_bbox),
        "ROUTE_BBOX": ",".join(str(x) for x in route_bbox),
        "COMPOSE_PROFILE": f"routing-city-{slug}",
    }
    subprocess.run(
        ["bash", str(ROOT / "scripts" / "city_pack_prepare_core.sh")],
        check=True,
        cwd=str(ROOT),
        env=env,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
