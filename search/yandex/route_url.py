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
) -> str:
    """
    Маршрут по координатам POI (rtext=lat,lon~lat,lon).

    Всегда пеший режим (rtt=pd) — варианты A/B/C это прогулки между точками.
    """
    _ = labels, transport
    points = _dedupe_points(points)
    if close_loop and len(points) >= 3:
        if haversine_km(points[0], points[-1]) >= 0.08:
            points = [*points, points[0]]
    if len(points) < 2:
        if points:
            p = points[0]
            label = labels[0] if labels else ""
            if label.strip() and city:
                text = f"{label.strip()}, {city}"
                return (
                    f"https://yandex.ru/maps/?text={quote(text)}"
                    f"&ll={p.lon},{p.lat}&z=16"
                )
            return f"https://yandex.ru/maps/?pt={p.lon},{p.lat}&z=15"
        return ""

    parts = [f"{p.lat},{p.lon}" for p in points[:max_stops]]
    params: dict[str, str] = {
        "mode": "routes",
        "rtext": "~".join(parts),
        "rtt": "pd",
    }
    first = points[0]
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
