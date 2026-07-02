"""Пешеходная маршрутизация через Yandex Router API (v2)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

from models.routes import GeoPoint, RouteGeometry
from search.yandex.client import get_api_key
from search.yandex.poi_filters import haversine_km
from search.yandex.route_url import parse_maps_route_points

logger = logging.getLogger(__name__)

_ROUTER_URL = "https://api.routing.yandex.net/v2/route"
_LAST_CALL = 0.0
_MIN_INTERVAL = 0.35
_CLOSE_M_KM = 0.08


@dataclass(frozen=True)
class WalkRouteResult:
    geometry: RouteGeometry
    distance_m: float
    duration_s: float


def _throttle() -> None:
    global _LAST_CALL
    elapsed = time.monotonic() - _LAST_CALL
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _LAST_CALL = time.monotonic()


def reference_points_for_router(maps_route_url: str) -> list[GeoPoint]:
    """Точки маршрута без замыкания кольца и дублей ближе 80 м."""
    points = list(parse_maps_route_points(maps_route_url))
    if len(points) >= 2 and haversine_km(points[0], points[-1]) < _CLOSE_M_KM:
        points = points[:-1]
    deduped: list[GeoPoint] = []
    for point in points:
        if not deduped or haversine_km(deduped[-1], point) >= _CLOSE_M_KM:
            deduped.append(point)
    return deduped


def _append_coord(coords: list[list[float]], lon: float, lat: float) -> None:
    pair = [lon, lat]
    if coords and coords[-1][0] == pair[0] and coords[-1][1] == pair[1]:
        return
    coords.append(pair)


def _parse_route_response(data: dict[str, Any]) -> WalkRouteResult | None:
    route = data.get("route")
    if not isinstance(route, dict):
        return None
    legs = route.get("legs")
    if not isinstance(legs, list):
        return None

    coords: list[list[float]] = []
    distance_m = 0.0
    duration_s = 0.0
    for leg in legs:
        if not isinstance(leg, dict) or leg.get("status") != "OK":
            return None
        steps = leg.get("steps")
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, dict):
                continue
            distance_m += float(step.get("length") or 0)
            duration_s += float(step.get("duration") or 0)
            polyline = step.get("polyline")
            if not isinstance(polyline, dict):
                continue
            points = polyline.get("points")
            if not isinstance(points, list):
                continue
            for raw in points:
                if not isinstance(raw, (list, tuple)) or len(raw) < 2:
                    continue
                lat = float(raw[0])
                lon = float(raw[1])
                _append_coord(coords, lon, lat)

    if len(coords) < 2:
        return None
    return WalkRouteResult(
        geometry=RouteGeometry(coordinates=coords),
        distance_m=distance_m,
        duration_s=duration_s,
    )


def fetch_walk_route(points: list[GeoPoint]) -> WalkRouteResult | None:
    """Строит пеший маршрут по waypoints; при ошибке возвращает None."""
    api_key = get_api_key()
    if not api_key or len(points) < 2:
        return None

    waypoints = "|".join(f"{point.lat},{point.lon}" for point in points)
    _throttle()
    try:
        response = requests.get(
            _ROUTER_URL,
            params={
                "apikey": api_key,
                "waypoints": waypoints,
                "mode": "walking",
            },
            timeout=30,
        )
    except requests.RequestException:
        logger.warning("Yandex Router API request failed", exc_info=True)
        return None

    if response.status_code != 200:
        logger.warning(
            "Yandex Router API HTTP %s: %s",
            response.status_code,
            response.text[:300],
        )
        return None

    try:
        payload = response.json()
    except ValueError:
        logger.warning("Yandex Router API returned non-JSON body")
        return None

    if isinstance(payload, dict) and payload.get("errors"):
        logger.warning("Yandex Router API errors: %s", payload.get("errors"))
        return None

    if not isinstance(payload, dict):
        return None
    return _parse_route_response(payload)


def fetch_walk_route_for_maps_url(maps_route_url: str) -> WalkRouteResult | None:
    points = reference_points_for_router(maps_route_url)
    return fetch_walk_route(points)
