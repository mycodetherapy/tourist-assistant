"""POI-остановки маршрутов для голосования и пересборки."""

from __future__ import annotations

from typing import Any

from models.routes import RouteProgram
from program.item_key import make_route_stop_key
from program.parse_items import ParsedSection


def collect_route_stop_poi_ids(program: dict[str, Any]) -> dict[str, str]:
    """poi_id -> narrative для всех leisure-остановок программы."""
    raw = program.get("routes")
    if not isinstance(raw, dict):
        return {}
    try:
        routes = RouteProgram.model_validate(raw)
    except Exception:
        return {}
    out: dict[str, str] = {}
    for case in routes.cases:
        for stop in case.stops:
            if stop.kind != "leisure" or not stop.poi_id:
                continue
            label = (stop.narrative or "").strip() or stop.poi_id
            out.setdefault(stop.poi_id, label)
    return out


def parse_route_stops(program: dict[str, Any]) -> ParsedSection:
    """Голосуемые POI из structured routes (уникальные poi_id)."""
    poi_labels = collect_route_stop_poi_ids(program)
    if not poi_labels:
        return ParsedSection(intro="", items=())
    items = [f"{label} [{poi_id}]" for poi_id, label in poi_labels.items()]
    return ParsedSection(intro="", items=tuple(items))


def route_stop_keys_for_program(program: dict[str, Any]) -> set[str]:
    return {make_route_stop_key(pid) for pid in collect_route_stop_poi_ids(program)}
