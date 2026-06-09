"""Wikidata SPARQL: известные достопримечательности с координатами."""

from __future__ import annotations

import os
import time
from typing import Any
from urllib.parse import quote

import requests

from models.routes import GeoPoint, PoiPoint
from search.osm.nominatim import CityCenter
from search.osm.poi_from_tags import wikidata_row_to_poi
from search.yandex.poi_filters import (
    coord_key,
    poi_name_conflict,
    route_name_key,
    within_walkable_radius,
)

_WIKIDATA_SPARQL = os.getenv(
    "WIKIDATA_SPARQL_URL", "https://query.wikidata.org/sparql"
).rstrip("/")
_LAST_CALL = 0.0
_MIN_INTERVAL = 1.0

# Типы: музей, памятник, парк, театр, tourist attraction… (без generic architecture)
_PLACE_CLASSES = (
    "wd:Q570116",  # tourist attraction
    "wd:Q33506",  # museum
    "wd:Q4989906",  # monument
    "wd:Q22746",  # urban park
    "wd:Q16970",  # church
    "wd:Q24354",  # theatre building
    "wd:Q16560",  # palace
    "wd:Q23413",  # castle
)


def _throttle() -> None:
    global _LAST_CALL
    elapsed = time.monotonic() - _LAST_CALL
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _LAST_CALL = time.monotonic()


def _sparql_for_city(wikidata_id: str) -> str:
    classes = " ".join(_PLACE_CLASSES)
    return f"""
SELECT ?item ?itemLabel ?coord WHERE {{
  BIND(wd:{wikidata_id} AS ?city)
  ?item wdt:P131* ?city.
  ?item wdt:P625 ?coord.
  ?item wdt:P31/wdt:P279* ?class.
  VALUES ?class {{ {classes} }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "ru,en". }}
}}
LIMIT 80
""".strip()


def _run_sparql(query: str) -> list[dict[str, Any]]:
    _throttle()
    try:
        response = requests.get(
            _WIKIDATA_SPARQL,
            params={"query": query, "format": "json"},
            headers={
                "User-Agent": "tourist-assistant/1.0",
                "Accept": "application/sparql-results+json",
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return []
    bindings = payload.get("results", {}).get("bindings") or []
    return [row for row in bindings if isinstance(row, dict)]


def _append_poi(
    collected: list[PoiPoint],
    seen_ids: set[str],
    seen_coords: set[str],
    seen_names: set[str],
    poi: PoiPoint,
    *,
    center: CityCenter,
) -> bool:
    if poi.poi_id in seen_ids:
        return False
    name_key = route_name_key(poi.name)
    if name_key in seen_names:
        return False
    for existing in collected:
        if poi_name_conflict(
            poi.name, poi.coordinates, existing.name, existing.coordinates
        ):
            return False
    if not within_walkable_radius(
        poi.coordinates, GeoPoint(lon=center.lon, lat=center.lat)
    ):
        return False
    key = coord_key(poi.coordinates)
    if key in seen_coords:
        return False
    seen_ids.add(poi.poi_id)
    seen_coords.add(key)
    seen_names.add(name_key)
    collected.append(poi)
    return True


def fetch_wikidata_leisure(
    city: str,
    center: CityCenter,
    *,
    wikidata_id: str | None = None,
    max_items: int = 40,
) -> list[PoiPoint]:
    qid = (wikidata_id or center.wikidata_id or "").strip()
    if not qid:
        return []
    if not qid.startswith("Q"):
        qid = qid
    rows = _run_sparql(_sparql_for_city(qid))
    collected: list[PoiPoint] = []
    seen_ids: set[str] = set()
    seen_coords: set[str] = set()
    seen_names: set[str] = set()
    for row in rows:
        if len(collected) >= max_items:
            break
        item = row.get("item") or {}
        label = row.get("itemLabel") or {}
        coord = row.get("coord") or {}
        qid_raw = str(item.get("value") or "").rsplit("/", 1)[-1]
        name = str(label.get("value") or "").strip()
        coord_literal = str(coord.get("value") or "")
        poi = wikidata_row_to_poi(
            qid=qid_raw,
            name=name,
            coord_literal=coord_literal,
            city_hint=city,
        )
        if poi is None:
            continue
        _append_poi(
            collected,
            seen_ids,
            seen_coords,
            seen_names,
            poi,
            center=center,
        )
    return collected
