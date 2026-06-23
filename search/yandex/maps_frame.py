"""URL маршрута в формате yandex.ru/maps/?from=mapframe (как кнопка виджета)."""

from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlparse

from models.routes import GeoPoint

# region/slug в пути yandex.ru/maps/{path}/
_CITY_YANDEX_PATH: dict[str, str] = {
    "казань": "43/kazan",
    "kazan": "43/kazan",
    "йошкар-ола": "48/yoshkar-ola",
    "yoshkar-ola": "48/yoshkar-ola",
    "кострома": "7/kostroma",
    "kostroma": "7/kostroma",
    "москва": "213/moscow",
    "moscow": "213/moscow",
    "санкт-петербург": "2/saint-petersburg",
    "saint-petersburg": "2/saint-petersburg",
    "нижний новгород": "47/nizhny-novgorod",
    "nizhny novgorod": "47/nizhny-novgorod",
    "самара": "51/samara",
    "samara": "51/samara",
    "ижевск": "44/izhevsk",
    "izhevsk": "44/izhevsk",
}


def city_yandex_maps_path(city: str) -> str:
    key = (city or "").strip().lower().replace("ё", "е")
    return _CITY_YANDEX_PATH.get(key, "")


def _ruri_for_point_count(point_count: int) -> str:
    return "~" * max(0, point_count - 1)


def _route_ll(points: list[GeoPoint]) -> tuple[float, float]:
    if not points:
        return 0.0, 0.0
    lon = sum(p.lon for p in points) / len(points)
    lat = sum(p.lat for p in points) / len(points)
    return lon, lat


def build_maps_frame_route_url(
    rtext: str,
    *,
    ll_lon: float,
    ll_lat: float,
    city: str = "",
    z: str = "15",
) -> str:
    """Полная ссылка на маршрут (как при клике «Открыть в Яндекс Картах» в iframe)."""
    parts = [chunk.strip() for chunk in rtext.split("~") if chunk.strip()]
    params = {
        "from": "mapframe",
        "source": "mapframe",
        "utm_source": "mapframe",
        "ll": f"{ll_lon},{ll_lat}",
        "mode": "routes",
        "rtext": rtext,
        "rtt": "pd",
        "ruri": _ruri_for_point_count(len(parts)),
        "z": z,
    }
    path = city_yandex_maps_path(city)
    base = f"https://yandex.ru/maps/{path}/" if path else "https://yandex.ru/maps/"
    return f"{base}?{urlencode(params)}"


def maps_frame_route_url_from_maps_url(maps_route_url: str, *, city: str = "") -> str:
    trimmed = (maps_route_url or "").strip()
    if not trimmed:
        return ""
    try:
        parsed = urlparse(trimmed)
        if "yandex" not in parsed.netloc:
            return ""
        query = parse_qs(parsed.query)
        rtext = (query.get("rtext") or [""])[0]
        if not rtext:
            return ""
        ll_raw = (query.get("ll") or [""])[0]
        if ll_raw and "," in ll_raw:
            lon_s, lat_s = ll_raw.split(",", 1)
            ll_lon, ll_lat = float(lon_s), float(lat_s)
        else:
            from search.yandex.route_url import parse_maps_route_points

            points = parse_maps_route_points(trimmed)
            ll_lon, ll_lat = _route_ll(points)
        z = (query.get("z") or ["15"])[0]
        return build_maps_frame_route_url(
            rtext,
            ll_lon=ll_lon,
            ll_lat=ll_lat,
            city=city,
            z=z,
        )
    except Exception:
        return ""
