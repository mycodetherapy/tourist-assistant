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
from search.yandex.poi_filters import (
    haversine_km,
    is_landmark_poi_name,
    poi_name_conflict,
    route_name_key,
)
from search.yandex.route_url import build_maps_route_url

_WALK_FACTOR = 1.35
_SPAN_SMALL_CITY_KM = 3.0
_MIN_ROUTE_KM_SMALL = 1.0
_MIN_ROUTE_KM_MEDIUM = 3.0
_MIN_ROUTE_KM_SHORT = 2.0
_MAX_ROUTE_KM_SHORT = 5.0
_KM_PER_STOP_TARGET = 2.5


@dataclass(frozen=True)
class RouteProfile:
    title: str
    target_km_min: float
    target_km_max: float
    min_stops: int
    max_stops: int
    max_leg_km: float
    abs_min_km: float


# Точки на карте: начало → промежуточные → конец (все — leisure из пула).
_BASE_PROFILES: dict[RouteCaseId, RouteProfile] = {
    "A": RouteProfile(
        title="Лёгкая прогулка (~4 км)",
        target_km_min=3.2,
        target_km_max=4.6,
        min_stops=3,
        max_stops=4,
        max_leg_km=2.2,
        abs_min_km=_MIN_ROUTE_KM_MEDIUM,
    ),
    "B": RouteProfile(
        title="Средний маршрут (5–6 км)",
        target_km_min=4.8,
        target_km_max=6.5,
        min_stops=4,
        max_stops=6,
        max_leg_km=2.6,
        abs_min_km=_MIN_ROUTE_KM_MEDIUM,
    ),
    "C": RouteProfile(
        title="Длинный маршрут (7–8 км)",
        target_km_min=6.5,
        target_km_max=8.8,
        min_stops=5,
        max_stops=10,
        max_leg_km=3.2,
        abs_min_km=_MIN_ROUTE_KM_MEDIUM,
    ),
}


def _landmark_pool(leisure: list[PoiPoint]) -> list[PoiPoint]:
    """Только достопримечательности; улицы из Geocoder не участвуют в маршруте."""
    filtered = [p for p in leisure if is_landmark_poi_name(p.name)]
    return filtered if len(filtered) >= 3 else leisure


def _pool_span_km(leisure: list[PoiPoint]) -> float:
    """Максимальное расстояние между POI в пуле (пеший коэффициент)."""
    if len(leisure) < 2:
        return 0.0
    max_d = 0.0
    for i in range(len(leisure)):
        for j in range(i + 1, len(leisure)):
            max_d = max(max_d, haversine_km(leisure[i].coordinates, leisure[j].coordinates))
    return max_d * _WALK_FACTOR


def _abs_min_route_km(span_km: float) -> float:
    if span_km < _SPAN_SMALL_CITY_KM:
        return _MIN_ROUTE_KM_SMALL
    return _MIN_ROUTE_KM_MEDIUM


def _centroid(leisure: list[PoiPoint]) -> GeoPoint:
    lon = sum(p.coordinates.lon for p in leisure) / len(leisure)
    lat = sum(p.coordinates.lat for p in leisure) / len(leisure)
    return GeoPoint(lon=lon, lat=lat)


def _farthest_index(leisure: list[PoiPoint]) -> int:
    center = _centroid(leisure)
    return max(
        range(len(leisure)),
        key=lambda i: haversine_km(center, leisure[i].coordinates),
    )


def _outlier_indices(leisure: list[PoiPoint], *, count: int = 2) -> set[int]:
    """Самые дальние POI от центра пула — для длинных маршрутов B/C, не для A."""
    if len(leisure) <= 4:
        return set()
    center = _centroid(leisure)
    ranked = sorted(
        range(len(leisure)),
        key=lambda i: haversine_km(center, leisure[i].coordinates),
        reverse=True,
    )
    return set(ranked[:count])


def _stops_for_pool(case_id: RouteCaseId, pool_size: int, span_km: float) -> tuple[int, int]:
    """min/max точек на карте с учётом размера пула и географического размаха."""
    base = _BASE_PROFILES[case_id]
    if pool_size >= 7:
        max_s = base.max_stops
        if case_id == "C" and span_km >= 5.0:
            max_s = min(pool_size, 10)
        return base.min_stops, max_s
    if pool_size >= 5:
        if case_id == "A":
            return (3, min(4, pool_size)) if pool_size >= 3 else (pool_size, pool_size)
        if case_id == "B":
            return 4, min(5, pool_size - 1) if pool_size <= 7 else min(6, pool_size)
        return 5, min(10, pool_size)
    if pool_size >= 3:
        if case_id == "A":
            return 3, min(4, pool_size)
        if case_id == "B":
            return min(4, pool_size), pool_size
        return min(5, pool_size), pool_size
    n = max(pool_size, 1)
    return n, n


def _adapt_profiles(leisure: list[PoiPoint]) -> dict[RouteCaseId, RouteProfile]:
    """Профили A/B/C с учётом пула и размаха города."""
    pool_size = len(leisure)
    span_km = _pool_span_km(leisure)
    abs_min = _abs_min_route_km(span_km)
    out: dict[RouteCaseId, RouteProfile] = {}
    for case_id in ("A", "B", "C"):
        base = _BASE_PROFILES[case_id]
        min_s, max_s = _stops_for_pool(case_id, pool_size, span_km)
        km_scale = 0.9 if pool_size < 5 else 1.0
        if case_id == "A":
            out[case_id] = RouteProfile(
                title=base.title,
                target_km_min=max(_MIN_ROUTE_KM_SHORT, base.target_km_min * km_scale * 0.9),
                target_km_max=min(_MAX_ROUTE_KM_SHORT, base.target_km_max * km_scale),
                min_stops=min_s,
                max_stops=max_s,
                max_leg_km=base.max_leg_km,
                abs_min_km=_MIN_ROUTE_KM_SHORT,
            )
            continue
        out[case_id] = RouteProfile(
            title=base.title,
            target_km_min=max(abs_min, base.target_km_min * km_scale),
            target_km_max=base.target_km_max * km_scale,
            min_stops=min_s,
            max_stops=max_s,
            max_leg_km=base.max_leg_km,
            abs_min_km=abs_min,
        )
    return out


def route_profile_for_case(case_id: str, *, pool_size: int) -> RouteProfile:
    key: RouteCaseId = case_id if case_id in _BASE_PROFILES else "A"  # type: ignore[assignment]
    dummy = [PoiPoint(poi_id="x", tag="landmarks", name="x", coordinates=GeoPoint(lon=0, lat=0), maps_url="")]
    profiles = _adapt_profiles(dummy * max(pool_size, 1))
    return profiles[key]


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


def _window_coords(leisure: list[PoiPoint], indices: list[int]) -> list[GeoPoint]:
    return [leisure[i].coordinates for i in indices]


def _poi_name_conflict(a: PoiPoint, b: PoiPoint) -> bool:
    return poi_name_conflict(a.name, a.coordinates, b.name, b.coordinates)


def _window_has_duplicate_names(leisure: list[PoiPoint], indices: list[int]) -> bool:
    for i, a_idx in enumerate(indices):
        for b_idx in indices[i + 1 :]:
            if _poi_name_conflict(leisure[a_idx], leisure[b_idx]):
                return True
    return False


def _leg_limit_km(profile: RouteProfile, span_km: float) -> float:
    """Допускает более длинные переходы, если город размашистый и нужен min km."""
    return max(
        profile.max_leg_km,
        profile.abs_min_km * 1.15,
        span_km * 0.45 if span_km > 0 else 0.0,
    )


def _legs_within_limit(coords: list[GeoPoint], max_leg_km: float) -> bool:
    return all(
        haversine_km(coords[i - 1], coords[i]) <= max_leg_km
        for i in range(1, len(coords))
    )


def _order_indices_by_path(leisure: list[PoiPoint], indices: list[int]) -> list[int]:
    """Упорядочивает выбранные POI жадным обходом (не обязательно подряд в ordered)."""
    if len(indices) <= 1:
        return list(indices)
    remaining = set(indices)
    center_lon = sum(leisure[i].coordinates.lon for i in indices) / len(indices)
    center_lat = sum(leisure[i].coordinates.lat for i in indices) / len(indices)
    center = GeoPoint(lon=center_lon, lat=center_lat)
    start = min(remaining, key=lambda i: haversine_km(center, leisure[i].coordinates))
    path = [start]
    remaining.remove(start)
    while remaining:
        last = path[-1]
        nxt = min(
            remaining,
            key=lambda i: haversine_km(leisure[last].coordinates, leisure[i].coordinates),
        )
        path.append(nxt)
        remaining.remove(nxt)
    return path


def _order_indices(leisure: list[PoiPoint]) -> list[int]:
    """Жадный порядок обхода всего пула: от центра к ближайшим соседям."""
    return _order_indices_by_path(leisure, list(range(len(leisure))))


def _target_stops_for_km(km: float, profile: RouteProfile) -> int:
    """Сколько точек нужно для длинного маршрута (~1 остановка на 2.5 км)."""
    if km < 4.0:
        return profile.min_stops
    needed = int(km / _KM_PER_STOP_TARGET) + 1
    return max(profile.min_stops, min(needed, profile.max_stops))


def _densify_window(
    leisure: list[PoiPoint],
    ordered: list[int],
    window: list[int],
    profile: RouteProfile,
) -> list[int]:
    """Добавляет промежуточные POI между соседними точками маршрута (не через весь пул)."""
    if len(window) < 2:
        return window
    path = _order_indices_by_path(leisure, window)
    coords = _window_coords(leisure, path)
    km = estimate_path_km(coords)
    target = _target_stops_for_km(km, profile)
    if len(path) >= target:
        return path

    enriched: list[int] = []
    for i, idx in enumerate(path):
        if i == 0:
            enriched.append(idx)
            continue
        prev_idx = path[i - 1]
        if prev_idx not in ordered or idx not in ordered:
            enriched.append(idx)
            continue
        prev_pos, curr_pos = ordered.index(prev_idx), ordered.index(idx)
        lo, hi = sorted((prev_pos, curr_pos))
        segment = ordered[lo : hi + 1]
        if len(segment) <= 4:
            for mid in segment[1:-1]:
                if mid in enriched:
                    continue
                trial = enriched + [mid, idx]
                if _window_has_duplicate_names(leisure, trial):
                    continue
                if len(trial) >= profile.max_stops:
                    break
                enriched.append(mid)
        enriched.append(idx)

    enriched = _order_indices_by_path(leisure, enriched)
    if _window_has_duplicate_names(leisure, enriched):
        return path
    return enriched if len(enriched) >= len(path) else path


def _extend_for_min_km(
    leisure: list[PoiPoint],
    window: list[int],
    profile: RouteProfile,
    ordered: list[int],
    *,
    span_km: float,
    compact: bool = False,
    max_km: float | None = None,
) -> list[int]:
    """Добирает POI, если маршрут короче abs_min_km (с потолком max_km для варианта A)."""
    leg_limit = profile.max_leg_km if compact else _leg_limit_km(profile, span_km)
    current = _order_indices_by_path(leisure, window)
    coords = _window_coords(leisure, current)
    if estimate_path_km(coords) >= profile.abs_min_km:
        return current

    used = set(current)
    extend_leg = leg_limit if compact else max(leg_limit, _novel_leg_limit_km(profile, span_km))
    for _ in range(profile.max_stops - len(current)):
        coords = _window_coords(leisure, current)
        km = estimate_path_km(coords)
        if km >= profile.abs_min_km:
            break
        if max_km is not None and km >= max_km:
            break
        best_idx: int | None = None
        best_km = km
        for idx in ordered:
            if idx in used:
                continue
            if _window_has_duplicate_names(leisure, current + [idx]):
                continue
            trial = _order_indices_by_path(leisure, current + [idx])
            trial_coords = _window_coords(leisure, trial)
            if not _legs_within_limit(trial_coords, extend_leg):
                continue
            trial_km = estimate_path_km(trial_coords)
            if max_km is not None and trial_km > max_km:
                continue
            if trial_km > best_km:
                best_km = trial_km
                best_idx = idx
        if best_idx is None:
            break
        used.add(best_idx)
        current = _order_indices_by_path(leisure, list(used))
    return current


def _trim_to_max_km(
    leisure: list[PoiPoint],
    indices: list[int],
    profile: RouteProfile,
    max_km: float,
) -> list[int]:
    """Укорачивает маршрут, убирая точки, если длина выше потолка."""
    current = _order_indices_by_path(leisure, indices)
    while len(current) > profile.min_stops:
        km = estimate_path_km(_window_coords(leisure, current))
        if km <= max_km:
            break
        drop: int | None = None
        best_km = km
        for idx in current:
            trial = _order_indices_by_path(leisure, [i for i in current if i != idx])
            if len(trial) < profile.min_stops:
                continue
            tk = estimate_path_km(_window_coords(leisure, trial))
            if tk < best_km:
                best_km = tk
                drop = idx
        if drop is None:
            break
        current = [i for i in current if i != drop]
        current = _order_indices_by_path(leisure, current)
    return current


def _trim_indices_to_profile(
    leisure: list[PoiPoint],
    indices: list[int],
    profile: RouteProfile,
) -> list[int]:
    """Урезает до max_stops, но оставляет доп. точку, если иначе не дотягиваем abs_min_km."""
    result = _order_indices_by_path(leisure, indices)
    while len(result) > profile.max_stops:
        shorter = result[:-1]
        if estimate_path_km(_window_coords(leisure, shorter)) >= profile.abs_min_km:
            result = shorter
        else:
            break
    return result


def _score_window(
    leisure: list[PoiPoint],
    window: list[int],
    profile: RouteProfile,
) -> float:
    if _window_has_duplicate_names(leisure, window):
        return -1e6
    coords = _window_coords(leisure, window)
    km = estimate_path_km(coords)
    if km < profile.abs_min_km:
        return km - profile.abs_min_km - 10.0
    if km < profile.target_km_min:
        return km - profile.target_km_min
    if km > profile.target_km_max * 1.35:
        return profile.target_km_max - km
    return 0.0


def _pick_window(
    leisure: list[PoiPoint],
    ordered: list[int],
    profile: RouteProfile,
    *,
    span_km: float,
    must_include: list[int] | None = None,
    avoid: set[int] | None = None,
    min_unique: int = 0,
    compact: bool = False,
    max_km: float | None = None,
) -> list[int]:
    """Подбирает участок пути: длина, число точек, без повторов названий."""
    n = len(ordered)
    if n == 0:
        return []
    leg_limit = profile.max_leg_km if compact else _leg_limit_km(profile, span_km)
    if must_include and not compact:
        leg_limit = max(leg_limit, _novel_leg_limit_km(profile, span_km))
    must = set(must_include or [])
    avoid_set = avoid or set()
    best: list[int] = []
    best_score = -1e9

    for start in range(n):
        for length in range(profile.min_stops, min(profile.max_stops, n - start) + 1):
            window = ordered[start : start + length]
            if must and not must.issubset(set(window)):
                continue
            ordered_window = _order_indices_by_path(leisure, window)
            if _window_has_duplicate_names(leisure, ordered_window):
                continue
            if avoid_set:
                unique_count = len(set(ordered_window) - avoid_set)
                if unique_count < min_unique:
                    continue
            coords = _window_coords(leisure, ordered_window)
            if not _legs_within_limit(coords, leg_limit):
                continue
            score = _score_window(leisure, ordered_window, profile)
            km = estimate_path_km(coords)
            mid = (profile.target_km_min + profile.target_km_max) / 2
            tie = len(ordered_window) * 0.12 - abs(km - mid) * 0.02
            if km >= profile.abs_min_km:
                tie += 5.0
            overlap = len(set(ordered_window) & avoid_set)
            tie -= overlap * 25.0
            tie += (len(ordered_window) - overlap) * 4.0
            total = score * 100 + tie
            if score >= 0.0:
                total += 50
            if total > best_score:
                best_score = total
                best = ordered_window

    if not best:
        seed = list(must) if must else ordered[: min(profile.max_stops, n)]
        best = _order_indices_by_path(leisure, seed)

    if must and not must.issubset(set(best)):
        best = _order_indices_by_path(leisure, list(must))

    best = _extend_for_min_km(
        leisure, best, profile, ordered, span_km=span_km, compact=compact, max_km=max_km
    )
    best = _densify_window(leisure, ordered, best, profile)
    best = _extend_for_min_km(
        leisure, best, profile, ordered, span_km=span_km, compact=compact, max_km=max_km
    )
    if max_km is not None:
        best = _trim_to_max_km(leisure, best, profile, max_km)

    if _window_has_duplicate_names(leisure, best):
        best = _filter_conflicting_indices(leisure, best)

    return best[: profile.max_stops]


def _filter_conflicting_indices(leisure: list[PoiPoint], indices: list[int]) -> list[int]:
    filtered: list[int] = []
    for idx in indices:
        poi = leisure[idx]
        if any(_poi_name_conflict(poi, leisure[keep]) for keep in filtered):
            continue
        filtered.append(idx)
    return _order_indices_by_path(leisure, filtered)


def _stops_from_indices(leisure: list[PoiPoint], indices: list[int]) -> list[RouteStop]:
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
    if stops:
        km = estimate_path_km([leisure[i].coordinates for i in indices])
        stops.append(
            RouteStop(
                order=stops[-1].order + 1,
                kind="transit_note",
                narrative=(
                    f"Пеший маршрут ~{km:.1f} км по достопримечательностям. "
                    "Рестораны — «Искать вдоль маршрута» в Яндекс.Картах."
                ),
            )
        )
    return stops


def _ranked_indices_from_case(
    case: TripRouteCase,
    leisure: list[PoiPoint],
) -> list[int]:
    """Индексы POI из черновика LLM в порядке остановок."""
    poi_to_idx = {p.poi_id: i for i, p in enumerate(leisure)}
    seed: list[int] = []
    for stop in sorted(case.stops, key=lambda s: s.order):
        if stop.kind != "leisure" or not stop.poi_id:
            continue
        idx = poi_to_idx.get(stop.poi_id)
        if idx is None or idx in seed:
            continue
        poi = leisure[idx]
        if any(_poi_name_conflict(poi, leisure[keep]) for keep in seed):
            continue
        seed.append(idx)
    return seed


def _indices_from_llm_ranking(
    case: TripRouteCase,
    leisure: list[PoiPoint],
    profile: RouteProfile,
    ordered: list[int],
    span_km: float,
    *,
    compact: bool = False,
    max_km: float | None = None,
) -> list[int] | None:
    """
    Ранжирование LLM: poi_id в порядке модели → проверка km/дублей → обрезка или добор.
    None — черновик не прошёл валидацию, нужен алгоритмический fallback.
    """
    seed = _ranked_indices_from_case(case, leisure)
    if not seed:
        return None

    leg_limit = profile.max_leg_km if compact else _leg_limit_km(profile, span_km)
    indices = seed[: profile.max_stops]
    coords = _window_coords(leisure, indices)
    if not _legs_within_limit(coords, leg_limit):
        indices = _order_indices_by_path(leisure, indices)
        if not _legs_within_limit(_window_coords(leisure, indices), leg_limit):
            return None

    if max_km is not None:
        while len(indices) > profile.min_stops:
            if estimate_path_km(_window_coords(leisure, indices)) <= max_km:
                break
            indices = indices[:-1]
        if estimate_path_km(_window_coords(leisure, indices)) > max_km:
            return None

    grow_limit = profile.max_stops + (1 if compact else 2)
    while (
        estimate_path_km(_window_coords(leisure, indices)) < profile.abs_min_km
        and len(indices) < grow_limit
    ):
        added = False
        for idx in ordered:
            if idx in indices:
                continue
            trial = _order_indices_by_path(leisure, indices + [idx])
            if _window_has_duplicate_names(leisure, trial):
                continue
            trial_coords = _window_coords(leisure, trial)
            if not _legs_within_limit(trial_coords, leg_limit):
                continue
            trial_km = estimate_path_km(trial_coords)
            if max_km is not None and trial_km > max_km:
                continue
            indices = trial
            added = True
            break
        if not added:
            break

    indices = _extend_for_min_km(
        leisure,
        indices,
        profile,
        ordered,
        span_km=span_km,
        compact=compact,
        max_km=max_km,
    )
    if max_km is not None:
        indices = _trim_to_max_km(leisure, indices, profile, max_km)

    if _window_has_duplicate_names(leisure, indices):
        indices = _filter_conflicting_indices(leisure, indices)

    coords = _window_coords(leisure, indices)
    km = estimate_path_km(coords)
    if len(indices) < profile.min_stops or km < profile.abs_min_km:
        return None
    if max_km is not None and km > max_km * 1.05:
        return None
    if not compact and not _legs_within_limit(coords, _leg_limit_km(profile, span_km)):
        if not _legs_within_limit(
            coords, _novel_leg_limit_km(profile, span_km)
        ):
            return None

    return _trim_indices_to_profile(leisure, indices, profile)


def _finalize_leisure_indices(
    case: TripRouteCase,
    leisure: list[PoiPoint],
    profile: RouteProfile,
    span_km: float,
    *,
    compact: bool = False,
    max_km: float | None = None,
) -> list[int]:
    """Собирает индексы POI для варианта: LLM-ранг или добор алгоритмом."""
    ordered = _order_indices(leisure)
    llm = _indices_from_llm_ranking(
        case,
        leisure,
        profile,
        ordered,
        span_km,
        compact=compact,
        max_km=max_km,
    )
    if llm is not None:
        return llm

    if seed := _ranked_indices_from_case(case, leisure):
        indices = _order_indices_by_path(leisure, seed)
        indices = _extend_for_min_km(
            leisure,
            indices,
            profile,
            ordered,
            span_km=span_km,
            compact=compact,
            max_km=max_km,
        )
        if max_km is not None:
            indices = _trim_to_max_km(leisure, indices, profile, max_km)
        if _window_has_duplicate_names(leisure, indices):
            indices = _filter_conflicting_indices(leisure, indices)
        coords = _window_coords(leisure, indices)
        if (
            len(indices) >= profile.min_stops
            and estimate_path_km(coords) >= profile.abs_min_km
        ):
            return _trim_indices_to_profile(leisure, indices, profile)

    return _pick_window(
        leisure,
        ordered,
        profile,
        span_km=span_km,
        compact=compact,
        max_km=max_km,
    )


def finalize_route_program(
    program: RouteProgram,
    materials: RouteMaterials,
    *,
    transport: str = "mixed",
) -> RouteProgram:
    index = _poi_index(materials)
    leisure = _landmark_pool(materials.leisure_points)
    profiles = _adapt_profiles(leisure)
    span_km = _pool_span_km(leisure)
    cases: list[TripRouteCase] = []
    for case in program.cases:
        profile = profiles[case.case_id if case.case_id in profiles else "A"]  # type: ignore[index]
        compact = case.case_id == "A"
        max_km = _MAX_ROUTE_KM_SHORT if case.case_id == "A" else None
        indices = _finalize_leisure_indices(
            case,
            leisure,
            profile,
            span_km,
            compact=compact,
            max_km=max_km,
        )
        valid_stops = _stops_from_indices(leisure, indices)
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
        f"Пул: {len(materials.leisure_points)} мест досуга"
        + (
            f", {len(materials.dining_options)} ресторанов"
            if materials.dining_options
            else ""
        )
        + f" ({materials.provider}). "
        "Варианты A/B/C — разная длина и число точек на карте (мин. 1–3 км пешком)."
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


def _novel_leg_limit_km(profile: RouteProfile, span_km: float) -> float:
    """Длинные переходы к «дальним» POI (музей за городом и т.п.)."""
    return max(_leg_limit_km(profile, span_km), span_km * 0.72)


def _novel_cluster_center(leisure: list[PoiPoint], novel: list[int]) -> GeoPoint:
    if not novel:
        return leisure[0].coordinates
    lon = sum(leisure[i].coordinates.lon for i in novel) / len(novel)
    lat = sum(leisure[i].coordinates.lat for i in novel) / len(novel)
    return GeoPoint(lon=lon, lat=lat)


def _pick_novel_route(
    leisure: list[PoiPoint],
    ordered: list[int],
    profile: RouteProfile,
    span_km: float,
    avoid: set[int],
) -> list[int]:
    """Маршрут C: в приоритете POI, которых нет в A/B."""
    novel = [i for i in range(len(leisure)) if i not in avoid]
    leg_limit = _novel_leg_limit_km(profile, span_km)

    if not novel:
        return []

    if len(novel) >= profile.min_stops:
        indices = _order_indices_by_path(leisure, novel)
        indices = _extend_for_min_km(leisure, indices, profile, ordered, span_km=span_km)
        return indices[: profile.max_stops]

    base = list(novel)
    center = _novel_cluster_center(leisure, novel)
    shared_sorted = sorted(
        [i for i in avoid if i in ordered],
        key=lambda i: haversine_km(center, leisure[i].coordinates),
    )
    while len(base) < profile.min_stops and shared_sorted:
        added = False
        for idx in shared_sorted:
            if idx in base:
                continue
            trial = _order_indices_by_path(leisure, base + [idx])
            if _window_has_duplicate_names(leisure, trial):
                continue
            coords = _window_coords(leisure, trial)
            if not _legs_within_limit(coords, leg_limit):
                continue
            base = trial
            added = True
            break
        if not added:
            break

    base = _extend_for_min_km(leisure, base, profile, ordered, span_km=span_km)
    if len(base) < profile.min_stops:
        used = set(base)
        for idx in shared_sorted:
            if idx in used:
                continue
            trial = _order_indices_by_path(leisure, base + [idx])
            if _window_has_duplicate_names(leisure, trial):
                continue
            coords = _window_coords(leisure, trial)
            if _legs_within_limit(coords, leg_limit):
                base = trial
                used.add(idx)
            if len(base) >= profile.min_stops:
                break

    base = _filter_conflicting_indices(leisure, base)
    return base[: profile.max_stops]


def _compute_algorithm_indices(
    leisure: list[PoiPoint],
    ordered: list[int],
    profiles: dict[RouteCaseId, RouteProfile],
    span_km: float,
) -> dict[RouteCaseId, list[int]]:
    """Индексы A/B/C чистым алгоритмом (fallback)."""
    outliers = _outlier_indices(leisure, count=2)
    far_idx = _farthest_index(leisure)

    a_idx = _pick_window(
        leisure,
        ordered,
        profiles["A"],
        span_km=span_km,
        avoid=outliers,
        compact=True,
        max_km=_MAX_ROUTE_KM_SHORT,
    )
    b_idx = _pick_window(
        leisure,
        ordered,
        profiles["B"],
        span_km=span_km,
        avoid=set(a_idx),
        min_unique=2,
    )
    c_idx = _pick_novel_route(
        leisure,
        ordered,
        profiles["C"],
        span_km,
        set(b_idx),
    )
    if len(c_idx) < profiles["C"].min_stops:
        outlier_must = [i for i in outliers if i not in set(b_idx)]
        c_must = outlier_must[:2] if outlier_must else (
            [far_idx] if far_idx not in set(b_idx) else None
        )
        c_idx = _pick_window(
            leisure,
            ordered,
            profiles["C"],
            span_km=span_km,
            avoid=set(b_idx),
            min_unique=2,
            must_include=c_must,
        )
    return {"A": a_idx, "B": b_idx, "C": c_idx}


def _trip_case_from_indices(
    case_id: RouteCaseId,
    indices: list[int],
    leisure: list[PoiPoint],
    profile: RouteProfile,
    city: str,
) -> TripRouteCase:
    km = estimate_path_km([leisure[i].coordinates for i in indices])
    return TripRouteCase(
        case_id=case_id,
        title=profile.title,
        summary=(
            f"Пешая прогулка по {city}: {profile.title.lower()}, "
            f"~{km:.1f} км, {len(indices)} остановок."
        ),
        stops=_stops_from_indices(leisure, indices)[:-1],
    )


def _draft_case_map(draft: RouteProgram) -> dict[RouteCaseId, TripRouteCase]:
    out: dict[RouteCaseId, TripRouteCase] = {}
    for case in draft.cases:
        cid = case.case_id
        if cid in ("A", "B", "C") and cid not in out:
            out[cid] = case  # type: ignore[assignment]
    return out


_HYBRID_MAX_OVERLAP = 0.85


def build_hybrid_route_program(
    materials: RouteMaterials,
    draft: RouteProgram,
    *,
    transport: str = "walking",
) -> RouteProgram:
    """
    LLM ранжирует poi_id по вариантам; алгоритм валидирует km/дубли или подставляет fallback.
    """
    leisure = _landmark_pool(materials.leisure_points)
    ordered = _order_indices(leisure)
    profiles = _adapt_profiles(leisure)
    span_km = _pool_span_km(leisure)
    algo = _compute_algorithm_indices(leisure, ordered, profiles, span_km)
    draft_cases = _draft_case_map(draft)

    indices_by_id: dict[RouteCaseId, list[int]] = {}
    for case_id in ("A", "B", "C"):
        profile = profiles[case_id]
        compact = case_id == "A"
        max_km = _MAX_ROUTE_KM_SHORT if case_id == "A" else None
        llm_idx: list[int] | None = None
        if case_id in draft_cases:
            llm_idx = _indices_from_llm_ranking(
                draft_cases[case_id],
                leisure,
                profile,
                ordered,
                span_km,
                compact=compact,
                max_km=max_km,
            )
        indices_by_id[case_id] = llm_idx if llm_idx is not None else algo[case_id]

    def _cases_from_indices() -> list[TripRouteCase]:
        return [
            _trip_case_from_indices(
                case_id,
                indices_by_id[case_id],
                leisure,
                profiles[case_id],
                materials.city,
            )
            for case_id in ("A", "B", "C")
        ]

    cases = _cases_from_indices()
    if len(cases) == 3:
        a, b, c = cases
        if leisure_overlap_ratio(b, c) > _HYBRID_MAX_OVERLAP:
            indices_by_id["C"] = algo["C"]
            cases = _cases_from_indices()
            a, b, c = cases
        if leisure_overlap_ratio(a, b) > _HYBRID_MAX_OVERLAP:
            indices_by_id["B"] = algo["B"]
            cases = _cases_from_indices()

    program = RouteProgram(cases=cases)
    return finalize_route_program(program, materials, transport=transport)


def build_fallback_route_program(materials: RouteMaterials) -> RouteProgram:
    """Три пеших варианта разной длины — только leisure из пула (алгоритм)."""
    leisure = _landmark_pool(materials.leisure_points)
    if not leisure:
        return RouteProgram(
            cases=[
                TripRouteCase(case_id=cid, title=f"Маршрут {cid}", summary="")
                for cid in ("A", "B", "C")
            ]
        )
    ordered = _order_indices(leisure)
    profiles = _adapt_profiles(leisure)
    span_km = _pool_span_km(leisure)
    algo = _compute_algorithm_indices(leisure, ordered, profiles, span_km)

    program = RouteProgram(
        cases=[
            _trip_case_from_indices(
                case_id, algo[case_id], leisure, profiles[case_id], materials.city
            )
            for case_id in ("A", "B", "C")
        ]
    )
    return finalize_route_program(program, materials, transport="walking")


def leisure_overlap_ratio(a: TripRouteCase, b: TripRouteCase) -> float:
    a_ids = {s.poi_id for s in a.stops if s.kind == "leisure" and s.poi_id}
    b_ids = {s.poi_id for s in b.stops if s.kind == "leisure" and s.poi_id}
    if not a_ids or not b_ids:
        return 1.0
    shared = len(a_ids & b_ids)
    denom = max(len(a_ids), len(b_ids))
    return shared / denom if denom else 1.0
