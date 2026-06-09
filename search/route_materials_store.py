"""Кэш пула POI по trip_id (section_artifacts)."""

from __future__ import annotations

import json
from typing import Any

from models.routes import PoiPoint, RouteMaterials
from search.yandex.materials import format_materials_digest

ROUTE_MATERIALS_SECTION = "route_materials"


def persist_route_materials_from_tool(
    trip_id: int,
    tool_content: str,
) -> bool:
    """Сохраняет materials после search_route_materials."""
    from db.repository import save_section_artifact

    try:
        data = json.loads(tool_content)
    except json.JSONDecodeError:
        return False
    materials_raw = data.get("materials")
    if not isinstance(materials_raw, dict):
        return False
    try:
        materials = RouteMaterials.model_validate(materials_raw)
    except Exception:
        return False
    payload: dict[str, Any] = {
        "schema_version": 1,
        "materials": materials.model_dump(),
        "poi_sources": data.get("poi_sources"),
        "landmark_discovery": data.get("landmark_discovery"),
        "leisure_count": data.get("leisure_count"),
    }
    digest = str(
        data.get("materials_digest") or data.get("digest") or ""
    ).strip() or format_materials_digest(materials)
    save_section_artifact(
        trip_id,
        ROUTE_MATERIALS_SECTION,
        payload,
        digest=digest,
    )
    return True


def load_route_materials_for_trip(trip_id: int) -> RouteMaterials | None:
    from db.repository import get_section_artifact

    row = get_section_artifact(trip_id, ROUTE_MATERIALS_SECTION)
    if not row:
        return None
    payload = row.get("payload") or {}
    raw = payload.get("materials")
    if not isinstance(raw, dict):
        return None
    try:
        return RouteMaterials.model_validate(raw)
    except Exception:
        return None


def persist_route_materials(
    trip_id: int,
    materials: RouteMaterials,
    *,
    overwrite: bool = False,
) -> bool:
    """Сохраняет RouteMaterials в section_artifacts."""
    from db.repository import get_section_artifact, save_section_artifact

    if not materials.leisure_points:
        return False
    if not overwrite:
        existing = get_section_artifact(trip_id, ROUTE_MATERIALS_SECTION)
        if existing:
            payload = existing.get("payload") or {}
            old = payload.get("materials")
            if isinstance(old, dict):
                try:
                    prev = RouteMaterials.model_validate(old)
                    if prev.leisure_points:
                        return False
                except Exception:
                    pass
    payload: dict[str, Any] = {
        "schema_version": 1,
        "materials": materials.model_dump(),
        "leisure_count": len(materials.leisure_points),
    }
    digest = format_materials_digest(materials)
    save_section_artifact(
        trip_id,
        ROUTE_MATERIALS_SECTION,
        payload,
        digest=digest,
    )
    return True


def extract_poi_pool_from_program(
    program: dict[str, Any],
    *,
    city: str,
    dates: str,
) -> RouteMaterials | None:
    """Собирает RouteMaterials из maps_route_url + stops (без записи в БД)."""
    from search.yandex.route_url import parse_maps_route_points

    routes = program.get("routes")
    if not isinstance(routes, dict):
        return None
    cases = routes.get("cases")
    if not isinstance(cases, list) or not cases:
        return None

    poi_by_id: dict[str, PoiPoint] = {}
    for case in cases:
        if not isinstance(case, dict):
            continue
        coords = parse_maps_route_points(str(case.get("maps_route_url", "")))
        if not coords:
            continue
        stops = case.get("stops")
        if not isinstance(stops, list):
            continue
        leisure_idx = 0
        for stop in stops:
            if not isinstance(stop, dict) or stop.get("kind") != "leisure":
                continue
            poi_id = str(stop.get("poi_id") or "").strip()
            if not poi_id or poi_id in poi_by_id:
                leisure_idx += 1
                continue
            coord = coords[leisure_idx] if leisure_idx < len(coords) else None
            leisure_idx += 1
            if coord is None:
                continue
            name = str(stop.get("narrative") or poi_id).strip() or poi_id
            poi_by_id[poi_id] = PoiPoint(
                poi_id=poi_id,
                tag="landmarks",
                name=name,
                coordinates=coord,
                maps_url=f"https://yandex.ru/maps/?pt={coord.lon},{coord.lat}&z=16",
            )

    if len(poi_by_id) < 3:
        return None
    return RouteMaterials(
        provider="osm",
        city=city,
        dates=dates,
        leisure_points=list(poi_by_id.values()),
    )


def backfill_route_materials_from_program(
    trip_id: int,
    program: dict[str, Any],
    *,
    city: str,
    dates: str,
) -> bool:
    """Восстанавливает пул POI из сохранённых маршрутов с maps_route_url."""
    if load_route_materials_for_trip(trip_id) is not None:
        return False
    materials = extract_poi_pool_from_program(program, city=city, dates=dates)
    if materials is None:
        return False
    return persist_route_materials(trip_id, materials)


def ensure_route_materials_for_trip(
    trip_id: int,
    *,
    city: str,
    dates: str,
    base_program: dict[str, Any] | None = None,
) -> RouteMaterials | None:
    """
    Загружает или восстанавливает пул POI: section_artifacts → base_program → история версий.
    """
    cached = load_route_materials_for_trip(trip_id)
    if cached is not None:
        return cached
    if base_program and backfill_route_materials_from_program(
        trip_id, base_program, city=city, dates=dates
    ):
        return load_route_materials_for_trip(trip_id)
    from db.repository import list_trip_itinerary_programs

    for program in list_trip_itinerary_programs(trip_id):
        if program is base_program:
            continue
        if backfill_route_materials_from_program(
            trip_id, program, city=city, dates=dates
        ):
            return load_route_materials_for_trip(trip_id)
    return None


def cached_materials_finalize_block(trip_id: int) -> str | None:
    """Текст для finalize: digest пула без нового поиска."""
    from db.repository import get_section_artifact

    row = get_section_artifact(trip_id, ROUTE_MATERIALS_SECTION)
    if not row:
        return None
    digest = str(row.get("digest") or "").strip()
    payload = row.get("payload") or {}
    leisure_count = payload.get("leisure_count")
    if not digest and payload.get("materials"):
        try:
            digest = format_materials_digest(
                RouteMaterials.model_validate(payload["materials"])
            )
        except Exception:
            return None
    if not digest:
        return None
    meta = {"leisure_count": leisure_count, "cached": True}
    body = json.dumps(
        {
            "category": "route_materials",
            "materials_digest": digest,
            "leisure_count": leisure_count,
            "instruction": (
                "Собери 3 пеших маршрута A/B/C разной длины из сохранённого пула POI. "
                "Используй ТОЛЬКО poi_id из materials_digest. "
                "Новый поиск не выполнялся."
            ),
            "warning": None,
            **meta,
        },
        ensure_ascii=False,
        indent=2,
    )
    return (
        "Результаты инструментов (кэш пула POI, без нового поиска):\n\n"
        f"### search_route_materials\n{body}"
    )
