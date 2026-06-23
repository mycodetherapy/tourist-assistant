#!/usr/bin/env python3
"""Скан extract.osm.pbf → poi.sqlite для city pack."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from search.osm.poi_from_tags import is_tagged_leisure_osm, osm_element_to_poi

try:
    import osmium
except ImportError as exc:
    raise SystemExit(
        "pyosmium не установлен. pip install osmium или prepare в Docker."
    ) from exc


def _in_bbox(lon: float, lat: float, bbox: tuple[float, float, float, float]) -> bool:
    west, south, east, north = bbox
    return west <= lon <= east and south <= lat <= north


def _way_center(way: osmium.osm.Way, node_locations: dict[int, tuple[float, float]]) -> tuple[float, float] | None:
    coords: list[tuple[float, float]] = []
    for node in way.nodes:
        loc = node_locations.get(node.ref)
        if loc is not None:
            coords.append(loc)
    if not coords:
        return None
    lon = sum(c[0] for c in coords) / len(coords)
    lat = sum(c[1] for c in coords) / len(coords)
    return lon, lat


class PoiExtractHandler(osmium.SimpleHandler):
    def __init__(self, *, poi_bbox: tuple[float, float, float, float], city_hint: str) -> None:
        super().__init__()
        self.poi_bbox = poi_bbox
        self.city_hint = city_hint
        self.node_locations: dict[int, tuple[float, float]] = {}
        self.pois: list[dict] = []

    def node(self, n: osmium.osm.Node) -> None:
        if not n.location.valid():
            return
        lon, lat = n.location.lon, n.location.lat
        self.node_locations[n.id] = (lon, lat)
        tags = {k: v for k, v in n.tags}
        if not is_tagged_leisure_osm(tags):
            return
        if not _in_bbox(lon, lat, self.poi_bbox):
            return
        element = {
            "type": "node",
            "id": n.id,
            "lat": lat,
            "lon": lon,
            "tags": tags,
        }
        poi = osm_element_to_poi(element, city_hint=self.city_hint)
        if poi is not None:
            self.pois.append(poi)

    def way(self, w: osmium.osm.Way) -> None:
        tags = {k: v for k, v in w.tags}
        if not is_tagged_leisure_osm(tags):
            return
        center = _way_center(w, self.node_locations)
        if center is None:
            return
        lon, lat = center
        if not _in_bbox(lon, lat, self.poi_bbox):
            return
        element = {
            "type": "way",
            "id": w.id,
            "center": {"lat": lat, "lon": lon},
            "tags": tags,
        }
        poi = osm_element_to_poi(element, city_hint=self.city_hint)
        if poi is not None:
            self.pois.append(poi)


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS poi (
            poi_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            lon REAL NOT NULL,
            lat REAL NOT NULL,
            leisure_tag TEXT NOT NULL,
            maps_url TEXT NOT NULL,
            address TEXT NOT NULL DEFAULT '',
            osm_tags_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_poi_leisure_tag ON poi(leisure_tag);
        CREATE INDEX IF NOT EXISTS idx_poi_name ON poi(name);
        """
    )


def write_poi_sqlite(
    pois: list,
    *,
    db_path: Path,
) -> int:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    try:
        _init_db(conn)
        for poi in pois:
            conn.execute(
                """
                INSERT OR REPLACE INTO poi
                (poi_id, name, lon, lat, leisure_tag, maps_url, address, osm_tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    poi.poi_id,
                    poi.name,
                    poi.coordinates.lon,
                    poi.coordinates.lat,
                    poi.tag,
                    poi.maps_url,
                    poi.address,
                    "{}",
                ),
            )
        conn.commit()
        return len(pois)
    finally:
        conn.close()


def build_index(
    *,
    extract_pbf: Path,
    db_path: Path,
    poi_bbox: tuple[float, float, float, float],
    city_hint: str,
) -> int:
    handler = PoiExtractHandler(poi_bbox=poi_bbox, city_hint=city_hint)
    handler.apply_file(str(extract_pbf), locations=True)
    return write_poi_sqlite(handler.pois, db_path=db_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build poi.sqlite from city extract PBF")
    parser.add_argument("extract_pbf", type=Path)
    parser.add_argument("db_path", type=Path)
    parser.add_argument("--west", type=float, required=True)
    parser.add_argument("--south", type=float, required=True)
    parser.add_argument("--east", type=float, required=True)
    parser.add_argument("--north", type=float, required=True)
    parser.add_argument("--city-hint", default="")
    args = parser.parse_args()
    bbox = (args.west, args.south, args.east, args.north)
    count = build_index(
        extract_pbf=args.extract_pbf,
        db_path=args.db_path,
        poi_bbox=bbox,
        city_hint=args.city_hint,
    )
    print(f"poi.sqlite: {count} записей → {args.db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
