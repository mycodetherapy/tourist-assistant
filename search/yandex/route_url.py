"""Сборка ссылки на маршрут Яндекс.Карт."""

from __future__ import annotations

from urllib.parse import quote, urlencode

from models.routes import GeoPoint


def _dedupe_points(points: list[GeoPoint]) -> list[GeoPoint]:
    if not points:
        return []
    out: list[GeoPoint] = [points[0]]
    for point in points[1:]:
        prev = out[-1]
        same = abs(point.lon - prev.lon) < 1e-4 and abs(point.lat - prev.lat) < 1e-4
        if not same:
            out.append(point)
    return out


def build_maps_route_url(
    points: list[GeoPoint],
    *,
    labels: list[str] | None = None,
    city: str = "",
    transport: str = "mixed",
    max_stops: int = 8,
) -> str:
    """
    Маршрут по координатам из пула POI (rtext=lat,lon~lat,lon).

    Координаты уже получены геокодером — так Яндекс строит точную линию маршрута.
    labels/city используются только для одиночной точки (fallback-ссылка).
    """
    _ = labels  # для одиночной точки ниже
    points = _dedupe_points(points)
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

    rtt = "pd" if transport in ("walking", "mixed") else "auto"
    parts = [f"{p.lat},{p.lon}" for p in points[:max_stops]]
    params = {"rtext": "~".join(parts), "rtt": rtt}
    return f"https://yandex.ru/maps/?{urlencode(params)}"
