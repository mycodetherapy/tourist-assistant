"""Пост-обработка маршрутов: URL карты, markdown, fallback."""

from __future__ import annotations

import re
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
    is_embankment_poi_name,
    is_landmark_poi_name,
    is_leisure_route_poi,
    poi_name_conflict,
    route_name_key,
)
from search.yandex.route_url import build_maps_route_url

_WALK_FACTOR = 1.35
_SPAN_SMALL_CITY_KM = 3.0
_MIN_ROUTE_KM_SMALL = 1.0
_MIN_ROUTE_KM_MEDIUM = 3.0
_MIN_ROUTE_KM_SHORT = 1.5
_MAX_ROUTE_KM_SHORT = 4.0
_ROUTE_MIN_STOPS = 3
_ROUTE_MAX_STOPS = 8
# Целевая плотность при densify: ~1 остановка на 300–400 м пути.
_KM_PER_STOP_DENSE = 0.35
_ROUTE_PARENS = re.compile(r"\s*\([^)]*\)")
_KM_SNIPPET = re.compile(r"~?\s*\d+(?:[.,]\d+)?\s*(?:–\s*\d+(?:[.,]\d+)?)?\s*км\.?", re.IGNORECASE)
_BRIDGE_NAME_RE = re.compile(r"\bмост\b", re.IGNORECASE)


def public_route_title(title: str) -> str:
    """Убирает подписи в скобках: «Лёгкая прогулка (~4 км)» → «Лёгкая прогулка»."""
    return _ROUTE_PARENS.sub("", title).strip()


def public_route_summary(summary: str) -> str:
    """Чистит legacy-summary от км и скобок."""
    text = _ROUTE_PARENS.sub("", summary)
    text = _KM_SNIPPET.sub("", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r",\s*,", ",", text)
    return text.strip(" ,:—-")


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
        title="Лёгкая прогулка",
        target_km_min=2.0,
        target_km_max=3.5,
        min_stops=_ROUTE_MIN_STOPS,
        max_stops=_ROUTE_MAX_STOPS,
        max_leg_km=1.2,
        abs_min_km=_MIN_ROUTE_KM_SHORT,
    ),
    "B": RouteProfile(
        title="Средний маршрут",
        target_km_min=4.0,
        target_km_max=5.5,
        min_stops=_ROUTE_MIN_STOPS,
        max_stops=_ROUTE_MAX_STOPS,
        max_leg_km=2.0,
        abs_min_km=_MIN_ROUTE_KM_MEDIUM,
    ),
    "C": RouteProfile(
        title="Длинный маршрут",
        target_km_min=6.0,
        target_km_max=8.5,
        min_stops=_ROUTE_MIN_STOPS,
        max_stops=_ROUTE_MAX_STOPS,
        max_leg_km=2.8,
        abs_min_km=_MIN_ROUTE_KM_MEDIUM,
    ),
}


def _landmark_pool(leisure: list[PoiPoint]) -> list[PoiPoint]:
    """POI для маршрута: достопримечательности и именованные пешеходные улицы."""
    filtered = [p for p in leisure if is_leisure_route_poi(p)]
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
    if not leisure:
        return GeoPoint(lon=0.0, lat=0.0)
    lon = sum(p.coordinates.lon for p in leisure) / len(leisure)
    lat = sum(p.coordinates.lat for p in leisure) / len(leisure)
    return GeoPoint(lon=lon, lat=lat)


def _farthest_index(leisure: list[PoiPoint]) -> int:
    if not leisure:
        return 0
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
    """min/max точек: сложность — по км, плотность — общий потолок для A/B/C."""
    del case_id, span_km
    max_s = min(_ROUTE_MAX_STOPS, max(pool_size, _ROUTE_MIN_STOPS))
    return _ROUTE_MIN_STOPS, max_s


def _pace_max_stops(case_id: RouteCaseId, max_stops: int, *, pace: str) -> int:
    """Темп влияет на целевые км, не на плотность остановок."""
    del case_id, pace
    return max_stops


def _pace_km_scale(pace: str) -> float:
    if pace == "relaxed":
        return 0.88
    if pace == "packed":
        return 1.08
    return 1.0


def _adapt_profiles(
    leisure: list[PoiPoint],
    *,
    pace: str = "moderate",
) -> dict[RouteCaseId, RouteProfile]:
    """Профили A/B/C с учётом пула, размаха города и темпа поездки."""
    pool_size = len(leisure)
    span_km = _pool_span_km(leisure)
    abs_min = _abs_min_route_km(span_km)
    km_scale = _pace_km_scale(pace)
    out: dict[RouteCaseId, RouteProfile] = {}
    for case_id in ("A", "B", "C"):
        base = _BASE_PROFILES[case_id]
        min_s, max_s = _stops_for_pool(case_id, pool_size, span_km)
        max_s = _pace_max_stops(case_id, max_s, pace=pace)
        min_s = min(min_s, max_s)
        pool_km_scale = 0.9 if pool_size < 5 else 1.0
        scale = pool_km_scale * km_scale
        if case_id == "A":
            out[case_id] = RouteProfile(
                title=base.title,
                target_km_min=max(_MIN_ROUTE_KM_SHORT, base.target_km_min * scale * 0.9),
                target_km_max=min(_MAX_ROUTE_KM_SHORT, base.target_km_max * scale),
                min_stops=min_s,
                max_stops=max_s,
                max_leg_km=base.max_leg_km,
                abs_min_km=_MIN_ROUTE_KM_SHORT,
            )
            continue
        out[case_id] = RouteProfile(
            title=base.title,
            target_km_min=max(abs_min, base.target_km_min * scale),
            target_km_max=base.target_km_max * scale,
            min_stops=min_s,
            max_stops=max_s,
            max_leg_km=base.max_leg_km,
            abs_min_km=abs_min,
        )
    return out


def estimate_path_km(coords: list[GeoPoint], *, close_loop: bool = False) -> float:
    if len(coords) < 2:
        return 0.0
    path = coords
    if close_loop and len(path) >= 3:
        path = [*path, path[0]]
    total = sum(
        haversine_km(path[i - 1], path[i]) for i in range(1, len(path))
    )
    return total * _WALK_FACTOR


def _is_embankment_poi(poi: PoiPoint, *, city_hint: str = "") -> bool:
    return poi.tag == "embankments" or is_embankment_poi_name(
        poi.name, city_hint=city_hint
    )


def _is_bridge_poi(poi: PoiPoint) -> bool:
    return bool(_BRIDGE_NAME_RE.search(poi.name))


def _wants_route_loop(
    case: TripRouteCase,
    leisure: list[PoiPoint],
    indices: list[int],
    span_km: float,
    *,
    city_hint: str = "",
) -> bool:
    if case.loop_route:
        return True
    if len(indices) < 3:
        return False
    selected = [leisure[i] for i in indices]
    embankments = sum(1 for poi in selected if _is_embankment_poi(poi, city_hint=city_hint))
    bridges = sum(1 for poi in selected if _is_bridge_poi(poi))
    if bridges >= 2 and embankments >= 1:
        return True
    if bridges >= 1 and embankments >= 1:
        return True
    if span_km < _SPAN_SMALL_CITY_KM and embankments >= 1:
        return True
    if span_km < _SPAN_SMALL_CITY_KM and len(indices) >= 4:
        return True
    return False


def _order_indices_for_loop(
    leisure: list[PoiPoint],
    indices: list[int],
    leg_limit: float,
) -> list[int]:
    """Переставляет точки так, чтобы замыкание кольца было короче."""
    if len(indices) <= 2:
        return list(indices)
    best_path = list(indices)
    best_close = float("inf")
    for start in indices:
        remaining = set(indices) - {start}
        path = [start]
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
        close_km = haversine_km(
            leisure[path[-1]].coordinates, leisure[path[0]].coordinates
        )
        coords = _window_coords(leisure, path)
        if close_km > leg_limit * 1.15:
            continue
        if not _legs_within_limit(coords, leg_limit):
            continue
        if close_km < best_close:
            best_close = close_km
            best_path = path
    return best_path


def _closing_leg_ok(
    leisure: list[PoiPoint],
    indices: list[int],
    profile: RouteProfile,
    span_km: float,
    *,
    compact: bool,
    max_km: float | None,
    leg_limit: float,
) -> bool:
    if len(indices) < 3:
        return False
    close_km = haversine_km(
        leisure[indices[-1]].coordinates, leisure[indices[0]].coordinates
    )
    if close_km > leg_limit * 1.15:
        return False
    loop_km = estimate_path_km(_window_coords(leisure, indices), close_loop=True)
    if max_km is not None and loop_km > max_km * 1.08:
        return False
    if compact and loop_km > _MAX_ROUTE_KM_SHORT * 1.05:
        return False
    if not compact and loop_km > profile.target_km_max * 1.35:
        return False
    return True


def _resolve_route_loop(
    case: TripRouteCase,
    leisure: list[PoiPoint],
    indices: list[int],
    span_km: float,
    profile: RouteProfile,
    *,
    compact: bool,
    max_km: float | None,
    city_hint: str = "",
) -> tuple[bool, list[int]]:
    if not _wants_route_loop(case, leisure, indices, span_km, city_hint=city_hint):
        return False, indices
    leg_limit = profile.max_leg_km if compact else _leg_limit_km(profile, span_km)
    reordered = _order_indices_for_loop(leisure, indices, leg_limit)
    if _closing_leg_ok(
        leisure,
        reordered,
        profile,
        span_km,
        compact=compact,
        max_km=max_km,
        leg_limit=leg_limit,
    ):
        return True, reordered
    return False, indices


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


def _profile_km_cap(
    profile: RouteProfile,
    *,
    compact: bool,
    max_km: float | None,
) -> float | None:
    """Потолок длины маршрута для trim/densify."""
    if max_km is not None:
        return max_km
    if compact:
        return min(_MAX_ROUTE_KM_SHORT, profile.target_km_max * 1.12)
    return profile.target_km_max * 1.15


def _greedy_route_from_pool(
    leisure: list[PoiPoint],
    ordered: list[int],
    pool: list[int],
    profile: RouteProfile,
    span_km: float,
    *,
    compact: bool,
    max_km: float | None,
    km_cap: float | None,
) -> list[int]:
    """Жадно собирает маршрут из pool в порядке ordered, не выходя за km_cap."""
    cap = km_cap or _profile_km_cap(profile, compact=compact, max_km=max_km)
    pool_set = set(pool)
    leg_limit = profile.max_leg_km if compact else _leg_limit_km(profile, span_km)
    indices: list[int] = []
    for idx in ordered:
        if idx not in pool_set:
            continue
        trial = _order_indices_by_path(leisure, indices + [idx])
        if _window_has_duplicate_names(leisure, trial):
            continue
        trial_coords = _window_coords(leisure, trial)
        if not _legs_within_limit(trial_coords, leg_limit):
            continue
        trial_km = estimate_path_km(trial_coords)
        if cap is not None and trial_km > cap and len(indices) >= profile.min_stops:
            continue
        if max_km is not None and trial_km > max_km:
            continue
        indices = trial
        if len(indices) >= profile.max_stops:
            break
    return indices


def _grow_leg_limit_km(
    profile: RouteProfile,
    span_km: float,
    *,
    compact: bool,
    below_abs_min: bool,
) -> float:
    """Лимит перехода при доборе длины до abs_min_km (короткий A может включить набережную)."""
    base = profile.max_leg_km if compact else _leg_limit_km(profile, span_km)
    if below_abs_min:
        return max(base, profile.abs_min_km * 1.15, 2.2)
    return base


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
    """Сколько точек добавить при densify (~1 остановка на 350 м пути)."""
    if km < 1.0:
        return profile.min_stops
    needed = int(km / _KM_PER_STOP_DENSE) + 1
    return max(profile.min_stops, min(needed, profile.max_stops))


def _densify_window(
    leisure: list[PoiPoint],
    ordered: list[int],
    window: list[int],
    profile: RouteProfile,
    *,
    km_cap: float | None = None,
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
        mids_added = 0
        for mid in segment[1:-1]:
            if mid in enriched:
                continue
            trial = enriched + [mid, idx]
            if _window_has_duplicate_names(leisure, trial):
                continue
            if len(trial) >= profile.max_stops:
                break
            trial_km = estimate_path_km(_window_coords(leisure, trial))
            if km_cap is not None and trial_km > km_cap:
                continue
            enriched.append(mid)
            mids_added += 1
            if mids_added >= 2:
                break
        enriched.append(idx)

    enriched = _order_indices_by_path(leisure, enriched)
    if _window_has_duplicate_names(leisure, enriched):
        return path
    result = enriched if len(enriched) >= len(path) else path
    if km_cap is not None:
        result = _trim_to_max_km(leisure, result, profile, km_cap)
    return result


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
    for _ in range(profile.max_stops - len(current)):
        coords = _window_coords(leisure, current)
        km = estimate_path_km(coords)
        if km >= profile.abs_min_km:
            break
        if max_km is not None and km >= max_km:
            break
        extend_leg = _grow_leg_limit_km(
            profile, span_km, compact=compact, below_abs_min=True
        )
        if not compact:
            extend_leg = max(extend_leg, _novel_leg_limit_km(profile, span_km))
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
    forbidden: set[int] | None = None,
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
    km_cap = _profile_km_cap(profile, compact=compact, max_km=max_km)
    must = set(must_include or [])
    avoid_set = avoid or set()
    forbidden_set = forbidden or set()
    best: list[int] = []
    best_score = -1e9

    for start in range(n):
        if ordered[start] in forbidden_set:
            continue
        for end in range(start + profile.min_stops, min(n, start + profile.max_stops) + 1):
            window = ordered[start:end]
            if must and not must.issubset(set(window)):
                continue
            ordered_window = _order_indices_by_path(leisure, window)
            if forbidden_set & set(ordered_window):
                continue
            if _window_has_duplicate_names(leisure, ordered_window):
                continue
            if avoid_set:
                unique_count = len(set(ordered_window) - avoid_set)
                if unique_count < min_unique:
                    continue
            coords = _window_coords(leisure, ordered_window)
            if not _legs_within_limit(coords, leg_limit):
                continue
            km = estimate_path_km(coords)
            if km > profile.target_km_max * 1.35:
                break
            if max_km is not None and km > max_km * 1.08:
                break
            score = _score_window(leisure, ordered_window, profile)
            mid = (profile.target_km_min + profile.target_km_max) / 2
            tie = (len(ordered_window) - profile.min_stops) * 0.25 - abs(km - mid) * 0.1
            if km >= profile.abs_min_km:
                tie += 5.0
            overlap = len(set(ordered_window) & avoid_set)
            tie -= overlap * 25.0
            tie += (len(ordered_window) - overlap) * 2.0
            total = score * 100 + tie
            if score >= 0.0:
                total += 50
            if total > best_score:
                best_score = total
                best = ordered_window

    if not best:
        available = [
            i
            for i in ordered
            if i not in forbidden_set and (not avoid_set or i not in avoid_set)
        ]
        pool = list(dict.fromkeys([*(must or []), *available])) or [
            i for i in ordered if i not in forbidden_set
        ]
        best = _greedy_route_from_pool(
            leisure,
            ordered,
            pool,
            profile,
            span_km,
            compact=compact,
            max_km=max_km,
            km_cap=km_cap,
        )
        if len(best) < profile.min_stops:
            shared = [i for i in ordered if i not in forbidden_set]
            best = _greedy_route_from_pool(
                leisure,
                ordered,
                shared,
                profile,
                span_km,
                compact=compact,
                max_km=max_km,
                km_cap=km_cap,
            )
        if len(best) < profile.min_stops:
            best = _order_indices_by_path(
                leisure, ordered[: min(profile.max_stops, n)]
            )

    if must and not must.issubset(set(best)):
        extra = [i for i in ordered if i not in best and i not in forbidden_set]
        seed = list(dict.fromkeys([*must, *extra]))[: profile.max_stops]
        best = _order_indices_by_path(leisure, seed)

    best = _extend_for_min_km(
        leisure, best, profile, ordered, span_km=span_km, compact=compact, max_km=max_km
    )
    best = _densify_window(leisure, ordered, best, profile, km_cap=km_cap)
    best = _extend_for_min_km(
        leisure, best, profile, ordered, span_km=span_km, compact=compact, max_km=max_km
    )
    if km_cap is not None:
        best = _trim_to_max_km(leisure, best, profile, km_cap)

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


def _route_summary(city: str, stop_count: int, *, loop: bool = False) -> str:
    kind = "Кольцевая пешая прогулка" if loop else "Пешая прогулка"
    return f"{kind} по {city}, {stop_count} остановок."


def _stops_from_indices(leisure: list[PoiPoint], indices: list[int]) -> list[RouteStop]:
    stops: list[RouteStop] = []
    for order, idx in enumerate(indices, start=1):
        poi = leisure[idx]
        stops.append(
            RouteStop(
                order=order,
                kind="leisure",
                poi_id=poi.poi_id,
                time_hint="",
                narrative=poi.name,
            )
        )
    if stops:
        stops.append(
            RouteStop(
                order=stops[-1].order + 1,
                kind="transit_note",
                narrative=(
                    "Пеший маршрут по достопримечательностям. "
                    "Рестораны — «Искать вдоль маршрута» в Яндекс.Картах."
                ),
            )
        )
    return stops


def _ranked_indices_from_case(
    case: TripRouteCase,
    leisure: list[PoiPoint],
    *,
    banned_poi_ids: set[str] | None = None,
) -> list[int]:
    """Индексы POI из черновика LLM в порядке остановок."""
    banned = banned_poi_ids or set()
    poi_to_idx = {p.poi_id: i for i, p in enumerate(leisure)}
    seed: list[int] = []
    for stop in sorted(case.stops, key=lambda s: s.order):
        if stop.kind != "leisure" or not stop.poi_id:
            continue
        if stop.poi_id in banned:
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
    banned_poi_ids: set[str] | None = None,
) -> list[int] | None:
    """
    Ранжирование LLM: poi_id в порядке модели → проверка km/дублей → обрезка или добор.
    None — черновик не прошёл валидацию, нужен алгоритмический fallback.
    """
    banned = banned_poi_ids or set()
    avoid_idx = _avoid_indices(leisure, banned)
    seed = _ranked_indices_from_case(case, leisure, banned_poi_ids=banned)
    if not seed:
        return None

    leg_limit = profile.max_leg_km if compact else _leg_limit_km(profile, span_km)
    indices = seed[: profile.max_stops]
    coords = _window_coords(leisure, indices)
    if not _legs_within_limit(coords, leg_limit):
        indices = _order_indices_by_path(leisure, indices)
        if not _legs_within_limit(_window_coords(leisure, indices), leg_limit):
            return None

    km_cap = _profile_km_cap(profile, compact=compact, max_km=max_km)
    if km_cap is not None:
        while len(indices) > profile.min_stops:
            if estimate_path_km(_window_coords(leisure, indices)) <= km_cap:
                break
            indices = indices[:-1]
        if estimate_path_km(_window_coords(leisure, indices)) > km_cap:
            return None

    grow_limit = profile.max_stops + (1 if compact else 2)
    while (
        estimate_path_km(_window_coords(leisure, indices)) < profile.abs_min_km
        and len(indices) < grow_limit
    ):
        added = False
        grow_leg = _grow_leg_limit_km(
            profile, span_km, compact=compact, below_abs_min=True
        )
        for idx in ordered:
            if idx in indices or idx in avoid_idx:
                continue
            trial = _order_indices_by_path(leisure, indices + [idx])
            if _window_has_duplicate_names(leisure, trial):
                continue
            trial_coords = _window_coords(leisure, trial)
            if not _legs_within_limit(trial_coords, grow_leg):
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
    banned_poi_ids: set[str] | None = None,
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
        banned_poi_ids=banned_poi_ids,
    )
    if llm is not None:
        return llm

    if seed := _ranked_indices_from_case(
        case, leisure, banned_poi_ids=banned_poi_ids
    ):
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

    forbidden = _avoid_indices(leisure, banned_poi_ids)
    return _pick_window(
        leisure,
        ordered,
        profile,
        span_km=span_km,
        compact=compact,
        max_km=max_km,
        avoid=forbidden,
        forbidden=forbidden,
    )


def _profile_for_case_id(case_id: str) -> str:
    if case_id in ("A", "B", "C"):
        return case_id
    if case_id.startswith("N-") and case_id[2:] in ("A", "B", "C"):
        return case_id[2:]
    return "A"


def _avoid_indices(
    leisure: list[PoiPoint],
    avoid_poi_ids: set[str] | None,
) -> set[int]:
    if not avoid_poi_ids:
        return set()
    id_to_idx = {p.poi_id: i for i, p in enumerate(leisure)}
    return {id_to_idx[pid] for pid in avoid_poi_ids if pid in id_to_idx}


def _needs_maps_backfill(program: RouteProgram) -> bool:
    if not program.cases:
        return False
    return any(not str(case.maps_route_url).strip() for case in program.cases)


def backfill_route_maps_only(
    program: RouteProgram,
    materials: RouteMaterials,
    *,
    transport: str = "mixed",
) -> RouteProgram:
    """Заполняет maps_route_url по уже выбранным остановкам, без переподбора POI."""
    if not _needs_maps_backfill(program):
        return program
    index = _poi_index(materials)
    leisure = _landmark_pool(materials.leisure_points)
    span_km = _pool_span_km(leisure)
    profiles = _adapt_profiles(leisure, pace="moderate")
    poi_to_idx = {p.poi_id: i for i, p in enumerate(leisure)}
    cases: list[TripRouteCase] = []
    for case in program.cases:
        if str(case.maps_route_url).strip():
            cases.append(case)
            continue
        points: list[GeoPoint] = []
        labels: list[str] = []
        for stop in sorted(case.stops, key=lambda s: s.order):
            if stop.kind != "leisure":
                continue
            coord = _coords_for_stop(stop, index)
            if coord is None:
                continue
            points.append(coord)
            labels.append(_label_for_stop(stop, index))
        profile_key = _profile_for_case_id(case.case_id)
        profile = profiles[profile_key]  # type: ignore[index]
        compact = profile_key == "A"
        max_km = _MAX_ROUTE_KM_SHORT if compact else None
        indices = [
            poi_to_idx[s.poi_id]
            for s in sorted(case.stops, key=lambda x: x.order)
            if s.kind == "leisure" and s.poi_id and s.poi_id in poi_to_idx
        ]
        close_loop, indices = _resolve_route_loop(
            case,
            leisure,
            indices,
            span_km,
            profile,
            compact=compact,
            max_km=max_km,
            city_hint=materials.city,
        )
        if indices:
            points = [leisure[i].coordinates for i in indices]
            labels = [leisure[i].name for i in indices]
        maps_url = ""
        if points:
            maps_url = build_maps_route_url(
                points,
                labels=labels,
                city=materials.city,
                transport=transport,
                max_stops=profile.max_stops + (1 if close_loop else 0),
                close_loop=close_loop,
            )
        cases.append(
            case.model_copy(
                update={
                    "maps_route_url": maps_url,
                    "loop_route": close_loop,
                }
            )
        )
    return program.model_copy(update={"cases": cases})


def _indices_for_loop_route(
    case: TripRouteCase,
    leisure: list[PoiPoint],
    indices: list[int],
    span_km: float,
    profile: RouteProfile,
    *,
    compact: bool,
    max_km: float | None,
    city_hint: str = "",
) -> list[int]:
    """Укорачивает маршрут, если кольцо с loop_route=True не замыкается."""
    if not case.loop_route:
        return indices
    trial = _order_indices_by_path(leisure, indices)
    while len(trial) > profile.min_stops:
        loop, reordered = _resolve_route_loop(
            case,
            leisure,
            trial,
            span_km,
            profile,
            compact=compact,
            max_km=max_km,
            city_hint=city_hint,
        )
        if loop:
            return reordered
        trial = trial[:-1]
        trial = _order_indices_by_path(leisure, trial)
    return indices


def _finalize_case_from_indices(
    case: TripRouteCase,
    indices: list[int],
    leisure: list[PoiPoint],
    profile: RouteProfile,
    materials: RouteMaterials,
    *,
    transport: str,
    span_km: float,
    compact: bool,
    max_km: float | None,
) -> TripRouteCase:
    indices = _indices_for_loop_route(
        case,
        leisure,
        indices,
        span_km,
        profile,
        compact=compact,
        max_km=max_km,
        city_hint=materials.city,
    )
    close_loop, indices = _resolve_route_loop(
        case,
        leisure,
        indices,
        span_km,
        profile,
        compact=compact,
        max_km=max_km,
        city_hint=materials.city,
    )
    points = [leisure[i].coordinates for i in indices]
    labels = [leisure[i].name for i in indices]
    return case.model_copy(
        update={
            "title": public_route_title(profile.title),
            "stops": _stops_from_indices(leisure, indices),
            "summary": _route_summary(materials.city, len(indices), loop=close_loop),
            "loop_route": close_loop,
            "maps_route_url": build_maps_route_url(
                points,
                labels=labels,
                city=materials.city,
                transport=transport,
                max_stops=profile.max_stops + (1 if close_loop else 0),
                close_loop=close_loop,
            ),
        }
    )


def finalize_route_program(
    program: RouteProgram,
    materials: RouteMaterials,
    *,
    transport: str = "mixed",
    pace: str = "moderate",
    banned_poi_ids: set[str] | None = None,
    prefer_poi_ids: set[str] | None = None,
) -> RouteProgram:
    del prefer_poi_ids  # учитывается в hybrid/enforce, не в finalize
    leisure = _landmark_pool(materials.leisure_points)
    if not leisure:
        return program.model_copy(
            update={
                "materials_summary": (
                    f"Пул: {len(materials.leisure_points)} мест досуга "
                    f"({materials.provider}). Недостаточно POI для маршрута на карте."
                ),
            }
        )
    profiles = _adapt_profiles(leisure, pace=pace)
    span_km = _pool_span_km(leisure)
    ordered = _order_indices(leisure)
    avoid_extra = _avoid_indices(leisure, banned_poi_ids)

    case_by_id: dict[RouteCaseId, TripRouteCase] = {}
    indices_by_id: dict[RouteCaseId, list[int]] = {}
    for case in program.cases:
        if case.preserved:
            continue
        profile_key = _profile_for_case_id(case.case_id)
        if profile_key not in ("A", "B", "C"):
            continue
        profile = profiles[profile_key]  # type: ignore[index]
        compact = profile_key == "A"
        max_km = _MAX_ROUTE_KM_SHORT if compact else None
        case_by_id[profile_key] = case
        indices_by_id[profile_key] = _finalize_leisure_indices(
            case,
            leisure,
            profile,
            span_km,
            compact=compact,
            max_km=max_km,
            banned_poi_ids=banned_poi_ids,
        )

    if len(indices_by_id) == 3:
        algo = _compute_algorithm_indices(
            leisure,
            ordered,
            profiles,
            span_km,
            avoid_extra=avoid_extra,
        )
        indices_by_id = _repair_route_indices_diversity(
            indices_by_id,
            leisure,
            ordered,
            profiles,
            span_km,
            algo,
            avoid_extra=avoid_extra,
        )
        if avoid_extra:
            indices_by_id = {
                case_id: [idx for idx in indices if idx not in avoid_extra]
                for case_id, indices in indices_by_id.items()
            }

    finalized: dict[RouteCaseId, TripRouteCase] = {}
    for case_id in ("A", "B", "C"):
        case = case_by_id.get(case_id)
        if case is None:
            continue
        profile = profiles[case_id]
        compact = case_id == "A"
        max_km = _MAX_ROUTE_KM_SHORT if compact else None
        finalized[case_id] = _finalize_case_from_indices(
            case,
            indices_by_id[case_id],
            leisure,
            profile,
            materials,
            transport=transport,
            span_km=span_km,
            compact=compact,
            max_km=max_km,
        )

    cases: list[TripRouteCase] = []
    for case in program.cases:
        if case.preserved:
            cases.append(case)
            continue
        profile_key = _profile_for_case_id(case.case_id)
        if profile_key in finalized:
            cases.append(finalized[profile_key])
        else:
            cases.append(case)
    summary = (
        f"Пул: {len(materials.leisure_points)} мест досуга"
        + (
            f", {len(materials.dining_options)} ресторанов"
            if materials.dining_options
            else ""
        )
        + f" ({materials.provider}). "
        "Варианты A/B/C — разная длина и число точек на карте."
    )
    return program.model_copy(update={"materials_summary": summary, "cases": cases})


def format_routes_text(program: RouteProgram) -> str:
    lines: list[str] = []
    if program.materials_summary:
        lines.append(program.materials_summary)
        lines.append("")
    for case in program.cases:
        lines.append(f"## Вариант {case.case_id}: {public_route_title(case.title)}")
        lines.append(public_route_summary(case.summary) or case.summary)
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
    km_cap = profile.target_km_max * 1.15

    if not novel:
        return []

    if len(novel) >= profile.min_stops:
        novel_sorted = sorted(novel, key=lambda i: ordered.index(i))
        indices: list[int] = []
        for idx in novel_sorted:
            trial = _order_indices_by_path(leisure, indices + [idx])
            if _window_has_duplicate_names(leisure, trial):
                continue
            trial_coords = _window_coords(leisure, trial)
            if not _legs_within_limit(trial_coords, leg_limit):
                continue
            trial_km = estimate_path_km(trial_coords)
            if trial_km > km_cap and len(indices) >= profile.min_stops:
                continue
            if len(trial) > profile.max_stops:
                break
            indices = trial
        if len(indices) >= profile.min_stops:
            indices = _extend_for_min_km(
                leisure, indices, profile, ordered, span_km=span_km
            )
            indices = _trim_to_max_km(leisure, indices, profile, km_cap)
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
    km_cap = profile.target_km_max * 1.15
    base = _trim_to_max_km(leisure, base, profile, km_cap)
    return base[: profile.max_stops]


def _clamp_indices_to_profile(
    leisure: list[PoiPoint],
    ordered: list[int],
    indices: list[int],
    profile: RouteProfile,
    span_km: float,
    *,
    compact: bool,
    max_km: float | None,
) -> list[int]:
    """Укладывает маршрут в km_cap; при невозможности — жадный пересбор из пула."""
    km_cap = _profile_km_cap(profile, compact=compact, max_km=max_km)
    if not indices or km_cap is None:
        return indices
    trimmed = _trim_to_max_km(leisure, indices, profile, km_cap)
    km = estimate_path_km(_window_coords(leisure, trimmed))
    if km <= km_cap and len(trimmed) >= profile.min_stops:
        return trimmed
    pool = [i for i in ordered if i not in set(trimmed) or i in trimmed]
    rebuilt = _greedy_route_from_pool(
        leisure,
        ordered,
        pool,
        profile,
        span_km,
        compact=compact,
        max_km=max_km,
        km_cap=km_cap,
    )
    if len(rebuilt) >= profile.min_stops:
        return rebuilt
    return trimmed if len(trimmed) >= profile.min_stops else indices


def _compute_algorithm_indices(
    leisure: list[PoiPoint],
    ordered: list[int],
    profiles: dict[RouteCaseId, RouteProfile],
    span_km: float,
    *,
    avoid_extra: set[int] | None = None,
    prefer_indices: list[int] | None = None,
) -> dict[RouteCaseId, list[int]]:
    """Индексы A/B/C чистым алгоритмом (fallback)."""
    if not leisure:
        return {"A": [], "B": [], "C": []}
    extra = avoid_extra or set()
    prefer = [i for i in (prefer_indices or []) if i not in extra]
    outliers = _outlier_indices(leisure, count=2)
    far_idx = _farthest_index(leisure)

    a_must = [prefer[0]] if prefer else None
    a_idx = _pick_window(
        leisure,
        ordered,
        profiles["A"],
        span_km=span_km,
        must_include=a_must,
        avoid=outliers | extra,
        forbidden=extra,
        compact=True,
        max_km=_MAX_ROUTE_KM_SHORT,
    )
    used_a = set(a_idx)
    b_prefer = next((i for i in prefer if i not in used_a), None)
    b_must = [b_prefer] if b_prefer is not None else None
    b_idx = _pick_window(
        leisure,
        ordered,
        profiles["B"],
        span_km=span_km,
        must_include=b_must,
        avoid=used_a | extra,
        forbidden=extra,
        min_unique=1,
    )
    used_b = set(b_idx)
    c_prefer = next((i for i in prefer if i not in used_a and i not in used_b), None)
    c_idx = _pick_novel_route(
        leisure,
        ordered,
        profiles["C"],
        span_km,
        used_b | extra,
    )
    if c_prefer is not None and c_prefer not in c_idx and c_prefer not in extra:
        trial = _order_indices_by_path(leisure, list(dict.fromkeys([*c_idx, c_prefer])))
        if len(trial) >= profiles["C"].min_stops:
            c_idx = trial[: profiles["C"].max_stops]
    c_km = estimate_path_km(_window_coords(leisure, c_idx)) if c_idx else 0.0
    if len(c_idx) < profiles["C"].min_stops or c_km < profiles["C"].target_km_min:
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
            forbidden=extra,
            min_unique=1,
            must_include=c_must,
        )
    out = {"A": a_idx, "B": b_idx, "C": c_idx}
    for case_id, idx in out.items():
        compact = case_id == "A"
        out[case_id] = _clamp_indices_to_profile(
            leisure,
            ordered,
            idx,
            profiles[case_id],
            span_km,
            compact=compact,
            max_km=_MAX_ROUTE_KM_SHORT if compact else None,
        )
    return out


def _trip_case_from_indices(
    case_id: RouteCaseId,
    indices: list[int],
    leisure: list[PoiPoint],
    profile: RouteProfile,
    city: str,
    *,
    loop_route: bool = False,
) -> TripRouteCase:
    return TripRouteCase(
        case_id=case_id,
        title=public_route_title(profile.title),
        summary=_route_summary(city, len(indices)),
        stops=_stops_from_indices(leisure, indices)[:-1],
        loop_route=loop_route,
    )


def _draft_case_map(draft: RouteProgram) -> dict[RouteCaseId, TripRouteCase]:
    out: dict[RouteCaseId, TripRouteCase] = {}
    for case in draft.cases:
        cid = case.case_id
        if cid in ("A", "B", "C") and cid not in out:
            out[cid] = case  # type: ignore[assignment]
    return out


_ROUTE_PAIR_OVERLAP_LIMITS: dict[tuple[RouteCaseId, RouteCaseId], float] = {
    ("A", "B"): 0.72,
    ("B", "C"): 0.76,
    ("A", "C"): 0.82,
}
CRITIC_ROUTE_PAIR_LIMITS: dict[tuple[RouteCaseId, RouteCaseId], float] = {
    ("A", "B"): 0.75,
    ("B", "C"): 0.78,
    ("A", "C"): 0.85,
}


def overlap_limits_for_pool(
    pool_size: int,
    *,
    limits: dict[tuple[RouteCaseId, RouteCaseId], float],
) -> dict[tuple[RouteCaseId, RouteCaseId], float]:
    """Ослабляет порог, если POI в пуле мало — иначе различить A/B/C невозможно."""
    if pool_size >= 12:
        return dict(limits)
    if pool_size >= 8:
        return {pair: min(0.92, ratio + 0.08) for pair, ratio in limits.items()}
    return {pair: 0.95 for pair in limits}


def _indices_overlap_ratio(a: list[int], b: list[int]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 1.0
    return len(sa & sb) / max(len(sa), len(sb))


def _repair_route_indices_diversity(
    indices_by_id: dict[RouteCaseId, list[int]],
    leisure: list[PoiPoint],
    ordered: list[int],
    profiles: dict[RouteCaseId, RouteProfile],
    span_km: float,
    algo: dict[RouteCaseId, list[int]],
    *,
    limits: dict[tuple[RouteCaseId, RouteCaseId], float] | None = None,
    avoid_extra: set[int] | None = None,
) -> dict[RouteCaseId, list[int]]:
    """Подменяет слишком похожие варианты алгоритмическим подбором с avoid."""
    limits = limits or overlap_limits_for_pool(
        len(leisure), limits=_ROUTE_PAIR_OVERLAP_LIMITS
    )
    banned = avoid_extra or set()
    out: dict[RouteCaseId, list[int]] = {
        cid: list(indices_by_id.get(cid) or []) for cid in ("A", "B", "C")
    }

    def _too_similar(left: RouteCaseId, right: RouteCaseId) -> bool:
        cap = limits.get((left, right), limits.get((right, left), 0.8))
        return _indices_overlap_ratio(out[left], out[right]) > cap

    if _too_similar("A", "B"):
        avoid = set(out["A"]) | banned
        repaired = _pick_window(
            leisure,
            ordered,
            profiles["B"],
            span_km=span_km,
            avoid=avoid,
            forbidden=banned,
            min_unique=1,
        )
        if repaired:
            out["B"] = repaired
        if _too_similar("A", "B"):
            out["B"] = list(algo.get("B") or out["B"])

    if _too_similar("B", "C"):
        avoid = set(out["B"]) | banned
        repaired = _pick_novel_route(
            leisure, ordered, profiles["C"], span_km, avoid
        )
        if repaired:
            out["C"] = repaired
        if _too_similar("B", "C"):
            out["C"] = list(algo.get("C") or out["C"])

    if _too_similar("A", "C"):
        avoid = set(out["A"]) | set(out["B"]) | banned
        repaired = _pick_novel_route(
            leisure, ordered, profiles["C"], span_km, avoid
        )
        if repaired:
            out["C"] = repaired
        if _too_similar("A", "C"):
            out["C"] = list(algo.get("C") or out["C"])

    return out


def _preferred_indices(
    leisure: list[PoiPoint],
    prefer_poi_ids: set[str] | None,
) -> list[int]:
    if not prefer_poi_ids:
        return []
    id_to_idx = {p.poi_id: i for i, p in enumerate(leisure)}
    return [id_to_idx[pid] for pid in prefer_poi_ids if pid in id_to_idx]


def build_hybrid_route_program(
    materials: RouteMaterials,
    draft: RouteProgram,
    *,
    transport: str = "walking",
    pace: str = "moderate",
    avoid_poi_ids: set[str] | None = None,
    prefer_poi_ids: set[str] | None = None,
) -> RouteProgram:
    """
    LLM ранжирует poi_id по вариантам; алгоритм валидирует km/дубли или подставляет fallback.
    """
    leisure = _landmark_pool(materials.leisure_points)
    if not leisure:
        return build_fallback_route_program(
            materials, pace=pace, avoid_poi_ids=avoid_poi_ids
        )
    ordered = _order_indices(leisure)
    profiles = _adapt_profiles(leisure, pace=pace)
    span_km = _pool_span_km(leisure)
    avoid_extra = _avoid_indices(leisure, avoid_poi_ids)
    prefer_indices = [
        i
        for i in _preferred_indices(leisure, prefer_poi_ids)
        if i not in avoid_extra
    ]
    algo = _compute_algorithm_indices(
        leisure,
        ordered,
        profiles,
        span_km,
        avoid_extra=avoid_extra,
        prefer_indices=prefer_indices,
    )
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
                banned_poi_ids=avoid_poi_ids,
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
                loop_route=(
                    draft_cases[case_id].loop_route if case_id in draft_cases else False
                ),
            )
            for case_id in ("A", "B", "C")
        ]

    indices_by_id = _repair_route_indices_diversity(
        indices_by_id,
        leisure,
        ordered,
        profiles,
        span_km,
        algo,
        avoid_extra=avoid_extra,
    )
    program = RouteProgram(cases=_cases_from_indices())
    return finalize_route_program(program, materials, transport=transport, pace=pace)


def build_fallback_route_program(
    materials: RouteMaterials,
    *,
    pace: str = "moderate",
    avoid_poi_ids: set[str] | None = None,
    prefer_poi_ids: set[str] | None = None,
    variant: int = 0,
) -> RouteProgram:
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
    if variant and ordered:
        shift = (variant * 3) % len(ordered)
        ordered = ordered[shift:] + ordered[:shift]
    profiles = _adapt_profiles(leisure, pace=pace)
    span_km = _pool_span_km(leisure)
    avoid_extra = _avoid_indices(leisure, avoid_poi_ids)
    prefer_indices = [
        i
        for i in _preferred_indices(leisure, prefer_poi_ids)
        if i not in avoid_extra
    ]
    algo = _compute_algorithm_indices(
        leisure,
        ordered,
        profiles,
        span_km,
        avoid_extra=avoid_extra,
        prefer_indices=prefer_indices,
    )

    program = RouteProgram(
        cases=[
            _trip_case_from_indices(
                case_id, algo[case_id], leisure, profiles[case_id], materials.city
            )
            for case_id in ("A", "B", "C")
        ]
    )
    return finalize_route_program(program, materials, transport="walking", pace=pace)


def leisure_overlap_ratio(a: TripRouteCase, b: TripRouteCase) -> float:
    a_ids = {s.poi_id for s in a.stops if s.kind == "leisure" and s.poi_id}
    b_ids = {s.poi_id for s in b.stops if s.kind == "leisure" and s.poi_id}
    if not a_ids or not b_ids:
        return 1.0
    shared = len(a_ids & b_ids)
    denom = max(len(a_ids), len(b_ids))
    return shared / denom if denom else 1.0


_PRESERVED_MAX_OVERLAP = 0.5


def routes_overlap_preserved(
    new_cases: list[TripRouteCase],
    preserved: list[TripRouteCase],
    *,
    max_ratio: float = _PRESERVED_MAX_OVERLAP,
) -> bool:
    for new_case in new_cases:
        for kept in preserved:
            if leisure_overlap_ratio(new_case, kept) > max_ratio:
                return True
    return False


def build_new_routes_respecting_likes(
    materials: RouteMaterials,
    draft: RouteProgram | None,
    preserved: list[TripRouteCase],
    *,
    transport: str = "walking",
    pace: str = "moderate",
    prefer_poi_ids: set[str] | None = None,
    banned_poi_ids: set[str] | None = None,
) -> RouteProgram:
    """Три новых маршрута с учётом poi из лайкнутых (без копирования пути)."""
    from program.route_feedback import collect_leisure_poi_ids

    avoid = collect_leisure_poi_ids(preserved) | set(banned_poi_ids or ())
    prefer = set(prefer_poi_ids or ()) - avoid
    program: RouteProgram | None = None
    for attempt in range(4):
        if draft is not None and attempt == 0:
            program = build_hybrid_route_program(
                materials,
                draft,
                transport=transport,
                pace=pace,
                avoid_poi_ids=avoid,
                prefer_poi_ids=prefer,
            )
        else:
            program = build_fallback_route_program(
                materials,
                pace=pace,
                avoid_poi_ids=avoid,
                prefer_poi_ids=prefer,
                variant=attempt,
            )
        if not routes_overlap_preserved(program.cases, preserved):
            return program
    return program or build_fallback_route_program(materials, pace=pace)


def enforce_route_poi_policy(
    program: RouteProgram,
    materials: RouteMaterials,
    *,
    banned_poi_ids: set[str],
    prefer_poi_ids: set[str],
    transport: str = "mixed",
    pace: str = "moderate",
) -> RouteProgram:
    """Убирает запрещённые POI из новых маршрутов; при необходимости пересобирает case."""
    if not banned_poi_ids:
        return program
    leisure = _landmark_pool(materials.leisure_points)
    if not leisure:
        return program
    ordered = _order_indices(leisure)
    profiles = _adapt_profiles(leisure, pace=pace)
    span_km = _pool_span_km(leisure)
    avoid_idx = _avoid_indices(leisure, banned_poi_ids)
    prefer_idx = [
        i for i in _preferred_indices(leisure, prefer_poi_ids) if i not in avoid_idx
    ]
    prefer_cursor = 0
    cases: list[TripRouteCase] = []
    for case in program.cases:
        if case.preserved:
            cases.append(case)
            continue
        stop_ids = {
            s.poi_id for s in case.stops if s.kind == "leisure" and s.poi_id
        }
        if not (stop_ids & banned_poi_ids):
            cases.append(case)
            continue
        profile_key = _profile_for_case_id(case.case_id)
        profile = profiles[profile_key]  # type: ignore[index]
        compact = profile_key == "A"
        max_km = _MAX_ROUTE_KM_SHORT if compact else None
        must = None
        if prefer_cursor < len(prefer_idx):
            must = [prefer_idx[prefer_cursor]]
            prefer_cursor += 1
        indices = _pick_window(
            leisure,
            ordered,
            profile,
            span_km=span_km,
            must_include=must,
            avoid=avoid_idx,
            forbidden=avoid_idx,
            compact=compact,
            max_km=max_km,
        )
        cases.append(
            _trip_case_from_indices(
                case.case_id,
                indices,
                leisure,
                profile,
                materials.city,
            )
        )
    patched = program.model_copy(update={"cases": cases})
    return finalize_route_program(
        patched,
        materials,
        transport=transport,
        pace=pace,
        banned_poi_ids=banned_poi_ids,
        prefer_poi_ids=prefer_poi_ids,
    )
