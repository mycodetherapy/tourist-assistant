#!/usr/bin/env python3
"""Пересобрать search/domestic_hub_coords.json через Nominatim (разово / при смене _CITY_IATA)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from search.city_codes import domestic_iata_hubs  # noqa: E402
from search.osm.nominatim import resolve_city_center  # noqa: E402

OUT = ROOT / "search" / "domestic_hub_coords.json"


def main() -> None:
    coords: dict[str, dict[str, object]] = {}
    for hub_key, iata, _label in domestic_iata_hubs():
        center = resolve_city_center(hub_key)
        if center is None:
            print(f"skip: {hub_key} ({iata})", file=sys.stderr)
            continue
        coords[hub_key] = {
            "lat": round(center.lat, 5),
            "lon": round(center.lon, 5),
            "iata": iata,
        }
    OUT.write_text(json.dumps(coords, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(coords)} hubs → {OUT}")


if __name__ == "__main__":
    main()
