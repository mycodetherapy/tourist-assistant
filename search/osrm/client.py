"""Клиент OSRM /route (пеший профиль).

Геометрия считается на сборке маршрута (worker), не в браузере:
- без подходящего URL — тихо возвращаем None (MapLibre рисует прямые);
- с OSRM — LineString GeoJSON [lon, lat] в route_geometry.

URL резолв (multi-city):
- OSRM_URL_BY_SLUG=kazan=http://osrm:5000,samara=http://osrm-samara:5000
- иначе OSRM_BASE_URL; если задан OSRM_DATASET и slug города другой — skip
  (один контейнер = один город, не слать Самару на граф Казани).
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


def parse_osrm_url_by_slug() -> dict[str, str]:
    """OSRM_URL_BY_SLUG=kazan=http://osrm:5000,samara=http://osrm-samara:5000"""
    raw = (os.getenv("OSRM_URL_BY_SLUG") or "").strip()
    if not raw:
        return {}
    out: dict[str, str] = {}
    for part in raw.split(","):
        chunk = part.strip()
        if not chunk or "=" not in chunk:
            continue
        slug, url = chunk.split("=", 1)
        slug_key = slug.strip()
        url_val = url.strip().rstrip("/")
        if slug_key and url_val:
            out[slug_key] = url_val
    return out


def resolve_osrm_base_url(city: str | None = None) -> str | None:
    """
    Базовый URL OSRM для города поездки.

    Возвращает None, если роутинг для этого города не настроен
    (не вызывать чужой граф).
    """
    slug: str | None = None
    if city and str(city).strip():
        try:
            from config.city_catalog import resolve_city_slug

            slug = resolve_city_slug(str(city))
        except Exception:
            logger.debug("resolve_city_slug failed for %r", city, exc_info=True)
            slug = None

    by_slug = parse_osrm_url_by_slug()
    if slug and slug in by_slug:
        return by_slug[slug]

    base = osrm_base_url()
    if not base:
        return None

    dataset = (os.getenv("OSRM_DATASET") or "").strip()
    if dataset and slug and slug != dataset:
        logger.info(
            "OSRM skip city=%r slug=%s dataset=%s (single-graph instance)",
            city,
            slug,
            dataset,
        )
        return None
    return base


def _waypoints_path(points: list[GeoPoint]) -> str:
    """OSRM: lon,lat;lon,lat — порядок важен."""
    return ";".join(f"{p.lon:.6f},{p.lat:.6f}" for p in points)


def fetch_foot_route(
    points: list[GeoPoint],
    *,
    base_url: str | None = None,
    city: str | None = None,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
) -> OsrmRouteResult | None:
    """
    Пеший маршрут через OSRM.

    Гарантии:
    - None при отсутствии URL, <2 точек, сетевой/HTTP ошибке, пустой геометрии;
    - не бросает наружу (сборка маршрута должна продолжаться без линии).
    """
    if base_url is not None:
        url_base = base_url.strip().rstrip("/")
    else:
        # Эфемерный роутер (VPS 4 ГБ): docker run на время запроса
        try:
            from search.osrm.ephemeral import ephemeral_enabled, fetch_foot_route_ephemeral

            if ephemeral_enabled() and city:
                from config.city_catalog import resolve_city_slug

                slug = resolve_city_slug(str(city))
                if slug:
                    return fetch_foot_route_ephemeral(
                        points, slug=slug, timeout_s=timeout_s
                    )
        except Exception:
            logger.warning("ephemeral OSRM path failed", exc_info=True)

        url_base = (resolve_osrm_base_url(city) or "").strip().rstrip("/")
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
