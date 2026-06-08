"""Пост-обработка маршрутов: URL карты, markdown, fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from models.routes import (
    DiningOption,
    GeoPoint,
    PoiPoint,
    RouteCaseId,
    RouteMaterials,
    RouteProgram,
    RouteStop,
    TripRouteCase,
)
from search.yandex.poi_filters import coord_key, haversine_km
from search.yandex.route_url import build_maps_route_url

_WALK_FACTOR = 1.35


@dataclass(frozen=True)
class RouteProfile:
    title: str
    target_km_min: float
    target_km_max: float
    min_stops: int
    max_stops: int
    max_leg_km: float


# Точки на карте: начало → промежуточные → конец (все — leisure из пула).
_BASE_PROFILES: dict[RouteCaseId, RouteProfile] = {
    "A": RouteProfile(
        title="Лёгкая прогулка (~4 км)",
        target_km_min=3.2,
        target_km_max=4.6,
        min_stops=3,
        max_stops=3,
        max_leg_km=2.2,
    ),
    "B": RouteProfile(
        title="Средний маршрут (5–6 км)",
        target_km_min=4.8,
        target_km_max=6.5,
        min_stops=4,
        max_stops=5,
        max_leg_km=2.6,
    ),
    "C": RouteProfile(
        title="Длинный маршрут (7–8 км)",
        target_km_min=6.5,
        target_km_max=8.8,
        min_stops=5,
        max_stops=7,
        max_leg_km=3.2,
    ),
}


def _stops_for_pool(case_id: RouteCaseId, pool_size: int) -> tuple[int, int]:
    """min/max точек на карте с учётом размера пула."""
    base = _BASE_PROFILES[case_id]
    if pool_size >= 7:
        return base.min_stops, base.max_stops
    if pool_size >= 5:
        if case_id == "A":
            return (3, 3) if pool_size >= 3 else (pool_size, pool_size)
        if case_id == "B":
            return 4, min(5, pool_size)
        return 5, min(7, pool_size)
    if pool_size >= 3:
        if case_id == "A":
            return 3, 3
        if case_id == "B":
            return min(4, pool_size), pool_size
        return min(5, pool_size), pool_size
    n = max(pool_size, 1)
    return n, n


def _adapt_profiles(pool_size: int) -> dict[RouteCaseId, RouteProfile]:
    """Уменьшает число точек, если в городе мало POI."""
    out: dict[RouteCaseId, RouteProfile] = {}
    for case_id in ("A", "B", "C"):
        base = _BASE_PROFILES[case_id]
        min_s, max_s = _stops_for_pool(case_id, pool_size)
        km_scale = 0.85 if pool_size < 5 else 1.0
        out[case_id] = RouteProfile(
            title=base.title,
            target_km_min=base.target_km_min * km_scale,
            target_km_max=base.target_km_max * km_scale,
            min_stops=min_s,
            max_stops=max_s,
            max_leg_km=base.max_leg_km,
        )
    return out


def route_profile_for_case(case_id: str, *, pool_size: int) -> RouteProfile:
    key: RouteCaseId = case_id if case_id in _BASE_PROFILES else "A"  # type: ignore[assignment]
    return _adapt_profiles(pool_size)[key]


def estimate_path_km(coords: list[GeoPoint]) -> float:
    if len(coords) < 2:
        return 0.0
    total = sum(
        haversine_km(coords[i - 1], coords[i]) for i in range(1, len(coords))
    )
    return total * _WALK_FACTOR


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


def _label_for_stop(stop: RouteStop, index: dict[str, Any]) -> str:
    if stop.narrative.strip():
        return stop.narrative.strip()
    if stop.poi_id and stop.poi_id in index:
        return index[stop.poi_id].name
    return ""


def _order_indices(leisure: list[PoiPoint]) -> list[int]:
    """Жадный порядок обхода: от центра пула к ближайшим соседям."""
    n = len(leisure)
    if n <= 1:
        return list(range(n))
    center_lon = sum(p.coordinates.lon for p in leisure) / n
    center_lat = sum(p.coordinates.lat for p in leisure) / n
    center = GeoPoint(lon=center_lon, lat=center_lat)
    remaining = set(range(n))
    start = min(
        remaining,
        key=lambda i: haversine_km(center, leisure[i].coordinates),
    )
    path = [start]
    remaining.remove(start)
    while remaining:
        last = path[-1]
        nxt = min(
            remaining,
            key=lambda i: haversine_km(
                leisure[last].coordinates, leisure[i].coordinates
            ),
        )
        path.append(nxt)
        remaining.remove(nxt)
    return path


def _window_coords(
    leisure: list[PoiPoint], ordered: list[int], window: list[int]
) -> list[GeoPoint]:
    return [leisure[i].coordinates for i in window]


def _score_window(
    leisure: list[PoiPoint],
    ordered: list[int],
    window: list[int],
    profile: RouteProfile,
) -> float:
    coords = _window_coords(leisure, ordered, window)
    km = estimate_path_km(coords)
    if km < profile.target_km_min:
        return km - profile.target_km_min
    if km > profile.target_km_max:
        return profile.target_km_max - km
    return 0.0


def _pick_window(
    leisure: list[PoiPoint],
    ordered: list[int],
    profile: RouteProfile,
    *,
    must_include: list[int] | None = None,
) -> list[int]:
    """Подбирает непрерывный участок упорядоченного пути под профиль длины."""
    n = len(ordered)
    if n == 0:
        return []
    must = set(must_include or [])
    best: list[int] = []
    best_score = -1e9

    for start in range(n):
        for length in range(profile.min_stops, min(profile.max_stops, n - start) + 1):
            window = ordered[start : start + length]
            if must and not must.issubset(set(window)):
                continue
            if length < profile.min_stops:
                continue
            coords = _window_coords(leisure, ordered, window)
            if any(
                haversine_km(coords[i - 1], coords[i]) > profile.max_leg_km
                for i in range(1, len(coords))
            ):
                continue
            score = _score_window(leisure, ordered, window, profile)
            km = estimate_path_km(coords)
            mid = (profile.target_km_min + profile.target_km_max) / 2
            tie = length * 0.05 - abs(km - mid) * 0.02
            if km < profile.target_km_min:
                tie += km * 0.1
            total = score * 100 + tie
            if score == 0.0:
                total += 50
            if total > best_score:
                best_score = total
                best = window

    if best:
        return best

    if must_include:
        extended = list(must_include)
        for idx in ordered:
            if idx in extended:
                continue
            trial = extended + [idx]
            if len(trial) > profile.max_stops:
                break
            coords = _window_coords(leisure, ordered, trial)
            if all(
                haversine_km(coords[i - 1], coords[i]) <= profile.max_leg_km
                for i in range(1, len(coords))
            ):
                extended = trial
            if len(extended) >= profile.min_stops:
                return extended[: profile.max_stops]

    return ordered[: min(profile.max_stops, n)]


def _compact_walkable_stops(
    stops: list[RouteStop],
    index: dict[str, Any],
    profile: RouteProfile,
) -> list[RouteStop]:
    """Leisure-цепочка под профиль варианта (длина и число точек)."""
    picked: list[RouteStop] = []
    last_coord: GeoPoint | None = None
    seen_coords: set[str] = set()

    for stop in sorted(stops, key=lambda s: s.order):
        if stop.kind != "leisure":
            continue
        coord = _coords_for_stop(stop, index)
        if coord is None:
            continue
        key = coord_key(coord)
        if key in seen_coords:
            continue
        if last_coord is not None and haversine_km(last_coord, coord) > profile.max_leg_km:
            continue
        seen_coords.add(key)
        picked.append(stop)
        last_coord = coord
        if len(picked) >= profile.max_stops:
            break

    if picked:
        km = estimate_path_km([_coords_for_stop(s, index) for s in picked])  # type: ignore[list-item]
        picked.append(
            RouteStop(
                order=picked[-1].order + 1,
                kind="transit_note",
                narrative=(
                    f"Пеший маршрут ~{km:.1f} км по достопримечательностям. "
                    "Рестораны — «Искать вдоль маршрута» в Яндекс.Картах."
                ),
            )
        )
    return picked


def finalize_route_program(
    program: RouteProgram,
    materials: RouteMaterials,
    *,
    transport: str = "mixed",
) -> RouteProgram:
    index = _poi_index(materials)
    pool_size = len(materials.leisure_points)
    cases: list[TripRouteCase] = []
    for case in program.cases:
        profile = route_profile_for_case(case.case_id, pool_size=pool_size)
        valid_stops = _compact_walkable_stops(case.stops, index, profile)
        points: list[GeoPoint] = []
        labels: list[str] = []
        for stop in valid_stops:
            if stop.kind != "leisure":
                continue
            coord = _coords_for_stop(stop, index)
            if coord is None:
                continue
            points.append(coord)
            labels.append(_label_for_stop(stop, index))
        cases.append(
            case.model_copy(
                update={
                    "stops": valid_stops,
                    "maps_route_url": build_maps_route_url(
                        points,
                        labels=labels,
                        city=materials.city,
                        transport=transport,
                        max_stops=profile.max_stops,
                    ),
                }
            )
        )
    summary = (
        f"Пул: {len(materials.leisure_points)} мест досуга, "
        f"{len(materials.dining_options)} ресторанов ({materials.provider}). "
        "Варианты A/B/C — 3 / 4–5 / 5–7 точек на карте, ~4 / 5–6 / 7–8 км пешком."
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
    """Три пеших варианта разной длины — только leisure из пула."""
    leisure = materials.leisure_points
    ordered = _order_indices(leisure)
    profiles = _adapt_profiles(len(leisure))
    small_city = len(leisure) <= 8

    a_idx = _pick_window(leisure, ordered, profiles["A"])
    b_idx = _pick_window(
        leisure,
        ordered,
        profiles["B"],
        must_include=a_idx if small_city else None,
    )
    c_idx = _pick_window(
        leisure,
        ordered,
        profiles["C"],
        must_include=b_idx if small_city else None,
    )

    def _case(case_id: RouteCaseId, indices: list[int]) -> TripRouteCase:
        profile = profiles[case_id]
        stops: list[RouteStop] = []
        for order, idx in enumerate(indices, start=1):
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
        km = estimate_path_km([poi.coordinates for poi in (leisure[i] for i in indices)])
        return TripRouteCase(
            case_id=case_id,
            title=profile.title,
            summary=(
                f"Пешая прогулка по {materials.city}: {profile.title.lower()}, "
                f"~{km:.1f} км, {len(indices)} остановок."
            ),
            stops=stops,
        )

    program = RouteProgram(
        cases=[
            _case("A", a_idx),
            _case("B", b_idx),
            _case("C", c_idx),
        ]
    )
    return finalize_route_program(program, materials, transport="walking")


def leisure_overlap_ratio(a: TripRouteCase, b: TripRouteCase) -> float:
    a_ids = {s.poi_id for s in a.stops if s.kind == "leisure" and s.poi_id}
    b_ids = {s.poi_id for s in b.stops if s.kind == "leisure" and s.poi_id}
    if not a_ids or not b_ids:
        return 1.0
    shared = len(a_ids & b_ids)
    return shared / max(len(a_ids), len(b_ids))
