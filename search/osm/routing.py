# Пешая маршрутизация через OSRM.

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

from config.settings import get_osrm_gateway_url, get_osrm_timeout, get_osrm_url, is_osrm_enabled
from models.routes import GeoPoint, RouteGeometry
from search.osm.city_pack import resolve_city_slug

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WalkRouteResult:
    geometry: RouteGeometry
    distance_m: float
    duration_s: float


def _format_waypoints(points: list[GeoPoint]) -> str:
    return ";".join(f"{point.lon},{point.lat}" for point in points)


def _routing_base_url() -> str | None:
    gateway = get_osrm_gateway_url()
    if gateway:
        return gateway
    if is_osrm_enabled():
        return get_osrm_url()
    return None


def fetch_walk_route(
    points: list[GeoPoint],
    *,
    city: str | None = None,
    city_slug: str | None = None,
) -> WalkRouteResult | None:
    """Строит пеший маршрут по waypoints; при ошибке возвращает None."""
    base = _routing_base_url()
    if not base:
        return None
    if len(points) < 2:
        return None

    slug = city_slug or (resolve_city_slug(city) if city else None)
    waypoints = _format_waypoints(points)
    url = f"{base}/route/v1/foot/{waypoints}"
    params: dict[str, str] = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
    }
    headers: dict[str, str] = {}
    if slug and get_osrm_gateway_url():
        params["city_slug"] = slug
        headers["X-City-Slug"] = slug

    try:
        response = requests.get(
            url, params=params, headers=headers, timeout=get_osrm_timeout()
        )
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
