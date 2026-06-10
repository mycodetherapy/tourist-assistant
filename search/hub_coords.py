"""Координаты IATA-хабов РФ (без Nominatim при поиске ближайшего аэропорта)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from search.city_codes import domestic_iata_hubs

_COORDS_PATH = Path(__file__).with_name("domestic_hub_coords.json")


@lru_cache(maxsize=1)
def domestic_hub_positions() -> tuple[tuple[str, str, float, float], ...]:
    """(iata, подпись, lat, lon) для всех российских хабов из справочника."""
    raw = json.loads(_COORDS_PATH.read_text(encoding="utf-8"))
    labels = {hub_key: label for hub_key, _iata, label in domestic_iata_hubs()}
    rows: list[tuple[str, str, float, float]] = []
    for hub_key, entry in raw.items():
        iata = str(entry.get("iata") or "").strip()
        if not iata:
            continue
        rows.append(
            (
                iata,
                labels.get(hub_key, hub_key),
                float(entry["lat"]),
                float(entry["lon"]),
            )
        )
    return tuple(rows)
