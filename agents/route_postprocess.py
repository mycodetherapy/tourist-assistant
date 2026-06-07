"""Пост-обработка маршрутов: URL карты, markdown, fallback."""

from __future__ import annotations

from typing import Any

from models.routes import (
    DiningOption,
    GeoPoint,
    PoiPoint,
    RouteMaterials,
    RouteProgram,
    RouteStop,
    TripRouteCase,
)
from search.yandex.route_url import build_maps_route_url


def _poi_index(materials: RouteMaterials) -> dict[str, PoiPoint | DiningOption]:
    index: dict[str, PoiPoint | DiningOption] = {}
    for poi in materials.leisure_points:
        index[poi.poi_id] = poi
    for dining in materials.dining_options:
        index[dining.poi_id] = dining
    return index


def _coords_for_stop(stop: RouteStop, index: dict[str, Any]) -> GeoPoint | None:
    if not stop.poi_id or stop.kind == "transit_note":
        return None
    item = index.get(stop.poi_id)
    if item is None:
        return None
    return item.coordinates


def finalize_route_program(
    program: RouteProgram,
    materials: RouteMaterials,
    *,
    transport: str = "mixed",
) -> RouteProgram:
    index = _poi_index(materials)
    cases: list[TripRouteCase] = []
    for case in program.cases:
        points: list[GeoPoint] = []
        valid_stops: list[RouteStop] = []
        for stop in case.stops:
            if stop.kind == "transit_note":
                valid_stops.append(stop)
                continue
            if stop.poi_id and stop.poi_id in index:
                valid_stops.append(stop)
                coord = _coords_for_stop(stop, index)
                if coord:
                    points.append(coord)
        cases.append(
            case.model_copy(
                update={
                    "stops": valid_stops,
                    "maps_route_url": build_maps_route_url(points, transport=transport),
                }
            )
        )
    summary = (
        f"Пул: {len(materials.leisure_points)} мест досуга, "
        f"{len(materials.dining_options)} ресторанов ({materials.provider})."
    )
    return program.model_copy(update={"materials_summary": summary, "cases": cases})


def format_routes_text(program: RouteProgram) -> str:
    lines: list[str] = []
    if program.materials_summary:
        lines.append(program.materials_summary)
        lines.append("")
    for case in program.cases:
        lines.append(f"## Вариант {case.case_id}: {case.title}")
        lines.append(case.summary)
        if case.maps_route_url:
            lines.append(f"[Маршрут на Яндекс.Картах]({case.maps_route_url})")
        for stop in sorted(case.stops, key=lambda s: s.order):
            hint = f" ({stop.time_hint})" if stop.time_hint else ""
            if stop.kind == "transit_note":
                lines.append(f"- Прогулка{hint}: {stop.narrative}")
            else:
                lines.append(f"- {stop.kind}{hint}: {stop.narrative} [poi_id={stop.poi_id}]")
        lines.append("")
    return "\n".join(lines).strip()


def build_fallback_route_program(materials: RouteMaterials) -> RouteProgram:
    """Три простых варианта без LLM."""
    leisure = materials.leisure_points
    dining = materials.dining_options
    dining_by_anchor: dict[str, list[DiningOption]] = {}
    for item in dining:
        dining_by_anchor.setdefault(item.anchor_poi_id, []).append(item)

    def _case(
        case_id: str,
        title: str,
        leisure_indices: list[int],
    ) -> TripRouteCase:
        stops: list[RouteStop] = []
        order = 1
        for idx in leisure_indices:
            if idx >= len(leisure):
                continue
            poi = leisure[idx]
            stops.append(
                RouteStop(
                    order=order,
                    kind="leisure",
                    poi_id=poi.poi_id,
                    time_hint="день",
                    narrative=poi.name,
                )
            )
            order += 1
            nearby = dining_by_anchor.get(poi.poi_id, [])
            if nearby:
                d = nearby[0]
                stops.append(
                    RouteStop(
                        order=order,
                        kind="dining",
                        poi_id=d.poi_id,
                        time_hint="обед или ужин",
                        narrative=d.name,
                    )
                )
                order += 1
        case = TripRouteCase(
            case_id=case_id,  # type: ignore[arg-type]
            title=title,
            summary=f"Маршрут по {materials.city}: {title}.",
            stops=stops,
        )
        return case

    indices = list(range(len(leisure)))
    a_idx = indices[: min(3, len(indices))]
    b_idx = indices[1 : min(4, len(indices))] or a_idx
    c_idx = list(reversed(indices[: min(3, len(indices))])) or a_idx

    program = RouteProgram(
        cases=[
            _case("A", "Классика и музеи", a_idx),
            _case("B", "Парки и видовые точки", b_idx),
            _case("C", "Альтернативный маршрут", c_idx),
        ]
    )
    return finalize_route_program(program, materials)


def leisure_overlap_ratio(a: TripRouteCase, b: TripRouteCase) -> float:
    a_ids = {s.poi_id for s in a.stops if s.kind == "leisure" and s.poi_id}
    b_ids = {s.poi_id for s in b.stops if s.kind == "leisure" and s.poi_id}
    if not a_ids or not b_ids:
        return 1.0
    shared = len(a_ids & b_ids)
    return shared / max(len(a_ids), len(b_ids))
