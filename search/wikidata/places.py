"""Wikidata SPARQL: известные достопримечательности с координатами."""

from __future__ import annotations

import os
import re
import time
from typing import Any

import requests

from models.routes import GeoPoint, PoiPoint
from search.osm.nominatim import CityCenter
from search.osm.poi_from_tags import wikidata_row_to_poi
from search.yandex.leisure_tags import infer_leisure_tag
from search.yandex.poi_filters import (
    coord_key,
    is_acceptable_place_name,
    is_embankment_poi_name,
    is_landmark_poi_name,
    poi_name_conflict,
    route_name_key,
    walkable_radius_km,
    within_walkable_radius,
)

_WIKIDATA_SPARQL = os.getenv(
    "WIKIDATA_SPARQL_URL", "https://query.wikidata.org/sparql"
).rstrip("/")
_SPARQL_TIMEOUT = int(os.getenv("WIKIDATA_SPARQL_TIMEOUT", "45"))
_SPARQL_RETRIES = max(1, int(os.getenv("WIKIDATA_SPARQL_RETRIES", "3")))
_SPARQL_RETRY_DELAY = float(os.getenv("WIKIDATA_SPARQL_RETRY_DELAY", "2"))
_LAST_CALL = 0.0
_MIN_INTERVAL = 1.0
_RETRYABLE_HTTP = frozenset({429, 500, 502, 503, 504})

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
    "wd:Q44613",  # monastery
    "wd:Q174782",  # square
    "wd:Q54114",  # boulevard
)

_BACKFILL_POSITIVE_RE = re.compile(
    r"ансамбл|комплекс|стен|башн|казарм|управ|мельниц|гимнази|театр|клуб|"
    r"памятник|мемориал|набереж|кремл|монаст|собор|церков|храм|музе|театр|"
    r"memorial|tomb|mosque|church|museum|palace|castle|monument|"
    r"embankment|promenade|waterfront",
    re.IGNORECASE,
)
_BACKFILL_NEGATIVE_RE = re.compile(
    r"^(?:доходный дом|дом,|дом [а-яё]|главный дом|флигель|лавк|богадельн|"
    r"сторожк|корпус мотальн|хозяйственн|каменная лавка|жилой дом|"
    r"административное здание)",
    re.IGNORECASE,
)

# Целевой размер пула: все Tier 0 + Tier 1 по score, но не больше cap.
DEFAULT_WIKIDATA_POOL_TARGET = 50


def _throttle() -> None:
    global _LAST_CALL
    elapsed = time.monotonic() - _LAST_CALL
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _LAST_CALL = time.monotonic()


def _sparql_for_city(wikidata_id: str) -> str:
    classes = " ".join(_PLACE_CLASSES)
    return f"""
SELECT ?item ?itemLabel ?coord ?sitelinks WHERE {{
  BIND(wd:{wikidata_id} AS ?city)
  ?item wdt:P131* ?city.
  ?item wdt:P625 ?coord.
  ?item wikibase:sitelinks ?sitelinks.
  ?item wdt:P31/wdt:P279* ?class.
  VALUES ?class {{ {classes} }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "ru,en". }}
}}
ORDER BY DESC(?sitelinks)
LIMIT 150
""".strip()


def _sparql_embankments_for_city(wikidata_id: str) -> str:
    """Набережные и променады по подписи (река/канал в городе)."""
    return f"""
SELECT ?item ?itemLabel ?coord ?sitelinks WHERE {{
  BIND(wd:{wikidata_id} AS ?city)
  ?item wdt:P131* ?city.
  ?item wdt:P625 ?coord.
  ?item wikibase:sitelinks ?sitelinks.
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "ru,en". }}
  FILTER(
    CONTAINS(LCASE(?itemLabel), "набереж") ||
    CONTAINS(LCASE(?itemLabel), "embankment") ||
    CONTAINS(LCASE(?itemLabel), "promenade") ||
    CONTAINS(LCASE(?itemLabel), "waterfront") ||
    CONTAINS(LCASE(?itemLabel), "riverside")
  )
}}
ORDER BY DESC(?sitelinks)
LIMIT 30
""".strip()


def _run_sparql(query: str) -> list[dict[str, Any]]:
    for attempt in range(_SPARQL_RETRIES):
        if attempt:
            time.sleep(_SPARQL_RETRY_DELAY * attempt)
        _throttle()
        try:
            response = requests.get(
                _WIKIDATA_SPARQL,
                params={"query": query, "format": "json"},
                headers={
                    "User-Agent": "tourist-assistant/1.0",
                    "Accept": "application/sparql-results+json",
                },
                timeout=_SPARQL_TIMEOUT,
            )
            if response.status_code in _RETRYABLE_HTTP:
                continue
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            continue
        bindings = payload.get("results", {}).get("bindings") or []
        return [row for row in bindings if isinstance(row, dict)]
    return []


def _row_qid(row: dict[str, Any]) -> str:
    item = row.get("item") or {}
    return str(item.get("value") or "").rsplit("/", 1)[-1]


def _dedupe_sparql_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Один Q-id — одна строка (SPARQL дублирует объекты с несколькими P31)."""
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        qid = _row_qid(row)
        if not qid or qid in seen:
            continue
        seen.add(qid)
        deduped.append(row)
    return deduped


def _fetch_city_rows(wikidata_id: str) -> list[dict[str, Any]]:
    main = _run_sparql(_sparql_for_city(wikidata_id))
    embankments = _run_sparql(_sparql_embankments_for_city(wikidata_id))
    return _dedupe_sparql_rows(main + embankments)


def _sitelinks_count(row: dict[str, Any]) -> int:
    raw = row.get("sitelinks") or {}
    try:
        return int(str(raw.get("value") or "0"))
    except ValueError:
        return 0


def _wikidata_backfill_score(name: str, *, sitelinks: int) -> float:
    """Эвристика значимости для soft-tier (без LLM)."""
    if _BACKFILL_NEGATIVE_RE.search(name.strip()):
        return 0.0
    score = min(sitelinks / 20.0, 1.0) * 0.5
    if _BACKFILL_POSITIVE_RE.search(name):
        score += 0.6
    lowered = name.lower()
    if lowered.startswith("здание"):
        score += 0.25
    return score


def _poi_tier(name: str, *, city: str) -> int | None:
    """0 strict landmark/embankment, 1 soft, None skip."""
    if is_landmark_poi_name(name, city_hint=city) or is_embankment_poi_name(
        name, city_hint=city
    ):
        return 0
    if not is_acceptable_place_name(name, city_hint=city):
        return None
    return 1


def _with_embankment_tag(poi: PoiPoint, name: str) -> PoiPoint:
    if poi.tag != "landmarks":
        return poi
    if infer_leisure_tag(name) == "embankments":
        return PoiPoint(
            poi_id=poi.poi_id,
            tag="embankments",
            name=poi.name,
            coordinates=poi.coordinates,
            maps_url=poi.maps_url,
            rating=poi.rating,
            address=poi.address,
        )
    return poi


def _append_poi(
    collected: list[PoiPoint],
    seen_ids: set[str],
    seen_coords: set[str],
    seen_names: set[str],
    poi: PoiPoint,
    *,
    center: CityCenter,
    city: str,
    relax_name_conflict: bool = False,
) -> bool:
    if poi.poi_id in seen_ids:
        return False
    name_key = route_name_key(poi.name)
    if name_key in seen_names:
        return False
    for existing in collected:
        if poi_name_conflict(
            poi.name,
            poi.coordinates,
            existing.name,
            existing.coordinates,
            relaxed=relax_name_conflict,
        ):
            return False
    if not within_walkable_radius(
        poi.coordinates,
        GeoPoint(lon=center.lon, lat=center.lat),
        max_km=walkable_radius_km(city),
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


def _fill_candidates(
    collected: list[PoiPoint],
    candidates: list[PoiPoint],
    *,
    center: CityCenter,
    city: str,
    max_items: int | None,
    relax_name_conflict: bool,
) -> None:
    seen_ids = {p.poi_id for p in collected}
    seen_coords = {coord_key(p.coordinates) for p in collected}
    seen_names = {route_name_key(p.name) for p in collected}
    for poi in candidates:
        if max_items is not None and len(collected) >= max_items:
            break
        if poi.poi_id in seen_ids:
            continue
        _append_poi(
            collected,
            seen_ids,
            seen_coords,
            seen_names,
            poi,
            center=center,
            city=city,
            relax_name_conflict=relax_name_conflict,
        )


def fetch_wikidata_leisure(
    city: str,
    center: CityCenter,
    *,
    wikidata_id: str | None = None,
    pool_target: int = DEFAULT_WIKIDATA_POOL_TARGET,
) -> list[PoiPoint]:
    """
    Wikidata POI: все Tier 0, затем Tier 1 по убыванию soft_score до pool_target.
    Если Tier 0 уже >= pool_target — Tier 1 не добавляем.
    """
    qid = (wikidata_id or center.wikidata_id or "").strip()
    if not qid:
        return []

    rows = _fetch_city_rows(qid)
    strict: list[PoiPoint] = []
    soft_scored: list[tuple[float, PoiPoint]] = []

    for row in rows:
        label = row.get("itemLabel") or {}
        coord = row.get("coord") or {}
        qid_raw = _row_qid(row)
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
        if not within_walkable_radius(
            poi.coordinates,
            GeoPoint(lon=center.lon, lat=center.lat),
            max_km=walkable_radius_km(city),
        ):
            continue
        poi = _with_embankment_tag(poi, name)
        tier = _poi_tier(name, city=city)
        if tier == 0:
            strict.append(poi)
        elif tier == 1:
            score = _wikidata_backfill_score(name, sitelinks=_sitelinks_count(row))
            if score > 0:
                soft_scored.append((score, poi))

    strict_candidates = strict
    soft_candidates = [poi for _, poi in sorted(soft_scored, key=lambda x: (-x[0], x[1].name))]

    collected: list[PoiPoint] = []
    _fill_candidates(
        collected,
        strict_candidates,
        center=center,
        city=city,
        max_items=None,
        relax_name_conflict=False,
    )
    _fill_candidates(
        collected,
        soft_candidates,
        center=center,
        city=city,
        max_items=pool_target,
        relax_name_conflict=False,
    )

    if len(collected) < pool_target:
        deferred = [
            p
            for p in strict_candidates + soft_candidates
            if p.poi_id not in {c.poi_id for c in collected}
        ]
        _fill_candidates(
            collected,
            deferred,
            center=center,
            city=city,
            max_items=pool_target,
            relax_name_conflict=True,
        )

    return collected
