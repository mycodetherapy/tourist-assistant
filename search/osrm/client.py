"""Клиент OSRM /route (пеший профиль).

Геометрия считается на сборке маршрута (worker), не в браузере:
- без OSRM_BASE_URL — тихо возвращаем None (MapLibre рисует прямые);
- с OSRM — LineString GeoJSON [lon, lat] в route_geometry.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from models.routes import GeoPoint, RouteGeometry

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_S = 8.0


@dataclass(frozen=True)
class OsrmRouteResult:
    geometry: RouteGeometry
    distance_m: float
    duration_s: float


def osrm_base_url() -> str:
    return (os.getenv("OSRM_BASE_URL") or "").strip().rstrip("/")


def _waypoints_path(points: list[GeoPoint]) -> str:
    """OSRM: lon,lat;lon,lat — порядок важен."""
    return ";".join(f"{p.lon:.6f},{p.lat:.6f}" for p in points)


def fetch_foot_route(
    points: list[GeoPoint],
    *,
    base_url: str | None = None,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
) -> OsrmRouteResult | None:
    """
    Пеший маршрут через OSRM.

    Гарантии:
    - None при отсутствии URL, <2 точек, сетевой/HTTP ошибке, пустой геометрии;
    - не бросает наружу (сборка маршрута должна продолжаться без линии).
    """
    url_base = (base_url if base_url is not None else osrm_base_url()).strip().rstrip("/")
    if not url_base or len(points) < 2:
        return None

    coords = _waypoints_path(points)
    # overview=full — вся линия; geometries=geojson — удобно класть в TripRouteCase
    request_url = (
        f"{url_base}/route/v1/foot/{quote(coords, safe=',;')}"
        f"?overview=full&geometries=geojson&steps=false"
    )
    try:
        with httpx.Client(timeout=timeout_s) as client:
            response = client.get(request_url)
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
    except Exception:
        logger.warning("OSRM route failed for %d waypoints", len(points), exc_info=True)
        return None

    if str(payload.get("code") or "").lower() != "ok":
        logger.warning("OSRM non-ok code=%s message=%s", payload.get("code"), payload.get("message"))
        return None

    routes = payload.get("routes")
    if not isinstance(routes, list) or not routes:
        return None
    route0 = routes[0]
    if not isinstance(route0, dict):
        return None

    geom_raw = route0.get("geometry")
    if not isinstance(geom_raw, dict):
        return None
    coords_raw = geom_raw.get("coordinates")
    if not isinstance(coords_raw, list) or len(coords_raw) < 2:
        return None

    coordinates: list[list[float]] = []
    for pair in coords_raw:
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            continue
        try:
            lon = float(pair[0])
            lat = float(pair[1])
        except (TypeError, ValueError):
            continue
        coordinates.append([lon, lat])
    if len(coordinates) < 2:
        return None

    try:
        distance_m = float(route0.get("distance") or 0.0)
        duration_s = float(route0.get("duration") or 0.0)
    except (TypeError, ValueError):
        distance_m, duration_s = 0.0, 0.0

    return OsrmRouteResult(
        geometry=RouteGeometry(type="LineString", coordinates=coordinates),
        distance_m=distance_m,
        duration_s=duration_s,
    )
