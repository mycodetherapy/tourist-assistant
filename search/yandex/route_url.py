"""Сборка ссылки на маршрут Яндекс.Карт."""

from __future__ import annotations

from urllib.parse import quote, urlencode

from models.routes import GeoPoint
from search.yandex.poi_filters import haversine_km


def _dedupe_points(points: list[GeoPoint]) -> list[GeoPoint]:
    """Убирает точки ближе ~80 м — иначе на карте «Кострома» и короткий маршрут."""
    if not points:
        return []
    out: list[GeoPoint] = [points[0]]
    for point in points[1:]:
        prev = out[-1]
        if haversine_km(point, prev) < 0.08:
            continue
        out.append(point)
    return out


def build_maps_route_url(
    points: list[GeoPoint],
    *,
    labels: list[str] | None = None,
    city: str = "",
    transport: str = "mixed",
    max_stops: int = 8,
    close_loop: bool = False,
    anchor_lat: float | None = None,
    anchor_lon: float | None = None,
    anchor_loop_end: bool = False,
) -> str:
    """
    Маршрут по координатам POI (rtext=lat,lon~lat,lon).

    Базовая точка (anchor) добавляется в начало и не входит в лимит max_stops POI.
    Всегда пеший режим (rtt=pd) — варианты A/B/C это прогулки между точками.
    """
    _ = labels, transport
    poi_points = _dedupe_points(points)[:max_stops]
    has_anchor = anchor_lat is not None and anchor_lon is not None
    if has_anchor:
        anchor_pt = GeoPoint(lat=float(anchor_lat), lon=float(anchor_lon))
        route_points: list[GeoPoint] = [anchor_pt, *poi_points]
        if anchor_loop_end and len(route_points) >= 2:
            if haversine_km(route_points[0], route_points[-1]) >= 0.08:
                route_points = [*route_points, anchor_pt]
    else:
        route_points = list(poi_points)
        if close_loop and len(route_points) >= 3:
            if haversine_km(route_points[0], route_points[-1]) >= 0.08:
                route_points = [*route_points, route_points[0]]
    if len(route_points) < 2:
        if route_points:
            p = route_points[0]
            label = labels[0] if labels else ""
            if label.strip() and city:
                text = f"{label.strip()}, {city}"
                return (
                    f"https://yandex.ru/maps/?text={quote(text)}"
                    f"&ll={p.lon},{p.lat}&z=16"
                )
            return f"https://yandex.ru/maps/?pt={p.lon},{p.lat}&z=15"
        return ""

    parts = [f"{p.lat},{p.lon}" for p in route_points]
    params: dict[str, str] = {
        "mode": "routes",
        "rtext": "~".join(parts),
        "rtt": "pd",
    }
    first = route_points[0]
    params["ll"] = f"{first.lon},{first.lat}"
    params["z"] = "14"
    return f"https://yandex.ru/maps/?{urlencode(params)}"


def parse_maps_route_points(url: str) -> list[GeoPoint]:
    """Координаты из deep link (rtext=lat,lon~…)."""
    from urllib.parse import parse_qs, urlparse

    trimmed = (url or "").strip()
    if not trimmed:
        return []
    try:
        parsed = urlparse(trimmed)
        rtext = parse_qs(parsed.query).get("rtext", [""])[0]
    except Exception:
        return []
    points: list[GeoPoint] = []
    for part in rtext.split("~"):
        chunk = part.strip()
        if not chunk or "," not in chunk:
            continue
        lat_s, lon_s = chunk.split(",", 1)
        try:
            points.append(GeoPoint(lat=float(lat_s), lon=float(lon_s)))
        except ValueError:
            continue
    return points
