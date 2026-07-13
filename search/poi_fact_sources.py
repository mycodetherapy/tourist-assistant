"""Контекст POI для on-demand справки (кэш-ключ, имя из route_materials)."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Literal

from config.city_catalog import get_city_pack_spec, resolve_city_slug
from search.osm.city_pack import is_pack_ready, pack_dir_for_slug
from search.route_materials_store import load_route_materials_for_trip

SourceKind = Literal["wikidata", "osm", "search"]

_WIKIDATA_QID_RE = re.compile(r"^Q\d+$", re.I)
_OSM_POI_RE = re.compile(r"^osm_(node|way|relation)_\d+$", re.I)


@dataclass(frozen=True)
class PoiFactContext:
    cache_key: str
    poi_id: str
    name: str
    city: str
    source_kind: SourceKind
    wikidata_qid: str | None


def extract_wikidata_qid(poi_id: str) -> str | None:
    raw = (poi_id or "").strip()
    if not raw:
        return None
    if _WIKIDATA_QID_RE.match(raw):
        return raw.upper()
    if raw.lower().startswith("wikidata_"):
        qid = raw.split("_", 1)[1].strip()
        if _WIKIDATA_QID_RE.match(qid):
            return qid.upper()
    return None


def is_wikidata_poi_id(poi_id: str) -> bool:
    return extract_wikidata_qid(poi_id) is not None


def is_osm_poi_id(poi_id: str) -> bool:
    return bool(_OSM_POI_RE.match((poi_id or "").strip()))


def infer_source_kind(poi_id: str) -> SourceKind:
    if is_wikidata_poi_id(poi_id):
        return "wikidata"
    if is_osm_poi_id(poi_id):
        return "osm"
    return "search"


def normalize_cache_key(*, poi_id: str | None, name: str, city: str) -> str:
    """Единый ключ кэша: QID, osm_* или hash по имени+городу."""
    pid = (poi_id or "").strip()
    qid = extract_wikidata_qid(pid)
    if qid:
        return qid
    if _OSM_POI_RE.match(pid):
        return pid
    blob = f"{city.strip().casefold()}|{name.strip().casefold()}"
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]
    return f"search_{digest}"


def _poi_db_path_for_city(city: str) -> str | None:
    slug = resolve_city_slug(city)
    if not slug or not is_pack_ready(slug):
        return None
    spec = get_city_pack_spec(slug)
    if spec is not None:
        path = spec.poi_db_path
        return str(path) if path.is_file() else None
    path = pack_dir_for_slug(slug) / "poi.sqlite"
    return str(path) if path.is_file() else None


def lookup_osm_wikidata_qid(poi_id: str, *, city: str) -> str | None:
    db_path = _poi_db_path_for_city(city)
    if not db_path:
        return None
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT osm_tags_json FROM poi WHERE poi_id = ? LIMIT 1",
            (poi_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row or not row[0]:
        return None
    try:
        tags = json.loads(row[0])
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(tags, dict):
        return None
    qid = str(tags.get("wikidata") or "").strip()
    return extract_wikidata_qid(qid)


def resolve_wikidata_qid(*, poi_id: str, city: str) -> str | None:
    qid = extract_wikidata_qid(poi_id)
    if qid:
        return qid
    if is_osm_poi_id(poi_id):
        return lookup_osm_wikidata_qid(poi_id, city=city)
    return None


def resolve_poi_context(
    *,
    trip_id: int,
    city: str,
    poi_id: str | None,
    name: str,
) -> PoiFactContext:
    pid = (poi_id or "").strip()
    display_name = (name or "").strip()

    materials = load_route_materials_for_trip(trip_id)
    if materials and pid:
        for poi in materials.leisure_points:
            if poi.poi_id == pid:
                display_name = poi.name.strip() or display_name
                break

    if not display_name:
        display_name = "Место"

    source_kind: SourceKind = infer_source_kind(pid) if pid else "search"
    wikidata_qid = resolve_wikidata_qid(poi_id=pid, city=city) if pid else None

    cache_key = normalize_cache_key(poi_id=pid or None, name=display_name, city=city)
    return PoiFactContext(
        cache_key=cache_key,
        poi_id=pid,
        name=display_name,
        city=city.strip(),
        source_kind=source_kind,
        wikidata_qid=wikidata_qid,
    )
