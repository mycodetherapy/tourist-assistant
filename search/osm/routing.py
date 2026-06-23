"""Пешеходная маршрутизация через OSRM."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

from config.settings import get_osrm_timeout, get_osrm_url, is_osrm_enabled
from models.routes import GeoPoint, RouteGeometry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WalkRouteResult:
    geometry: RouteGeometry
    distance_m: float
    duration_s: float


def _format_waypoints(points: list[GeoPoint]) -> str:
    return ";".join(f"{point.lon},{point.lat}" for point in points)


def fetch_walk_route(points: list[GeoPoint]) -> WalkRouteResult | None:
    """Строит пеший маршрут по waypoints; при ошибке возвращает None."""
    if not is_osrm_enabled():
        return None
    if len(points) < 2:
        return None

    base = get_osrm_url()
    waypoints = _format_waypoints(points)
    url = f"{base}/route/v1/foot/{waypoints}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
    }
    try:
        response = requests.get(url, params=params, timeout=get_osrm_timeout())
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("OSRM request failed: %s", exc)
        return None

    if payload.get("code") != "Ok":
        logger.warning("OSRM error: %s", payload.get("message", payload.get("code")))
        return None

    routes = payload.get("routes")
    if not isinstance(routes, list) or not routes:
        return None

    route = routes[0]
    geometry_raw = route.get("geometry")
    if not isinstance(geometry_raw, dict):
        return None
    if geometry_raw.get("type") != "LineString":
        return None
    coords = geometry_raw.get("coordinates")
    if not isinstance(coords, list) or len(coords) < 2:
        return None

    parsed_coords: list[list[float]] = []
    for item in coords:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        try:
            lon = float(item[0])
            lat = float(item[1])
        except (TypeError, ValueError):
            continue
        parsed_coords.append([lon, lat])

    if len(parsed_coords) < 2:
        return None

    try:
        distance_m = float(route.get("distance", 0))
        duration_s = float(route.get("duration", 0))
    except (TypeError, ValueError):
        distance_m = 0.0
        duration_s = 0.0

    return WalkRouteResult(
        geometry=RouteGeometry(coordinates=parsed_coords),
        distance_m=distance_m,
        duration_s=duration_s,
    )
