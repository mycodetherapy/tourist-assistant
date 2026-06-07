"""Сборка ссылки на маршрут Яндекс.Карт."""

from __future__ import annotations

from urllib.parse import urlencode

from models.routes import GeoPoint


def build_maps_route_url(
    points: list[GeoPoint],
    *,
    transport: str = "mixed",
) -> str:
    """Маршрут по цепочке координат (rtext=lat,lon~lat,lon)."""
    if len(points) < 2:
        if points:
            p = points[0]
            return f"https://yandex.ru/maps/?pt={p.lon},{p.lat}&z=15"
        return ""
    rtt = "pd" if transport in ("walking", "mixed") else "auto"
    parts = [f"{p.lat},{p.lon}" for p in points[:10]]
    params = {"rtext": "~".join(parts), "rtt": rtt}
    return f"https://yandex.ru/maps/?{urlencode(params)}"
