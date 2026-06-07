"""Поиск мест досуга по фиксированным тегам."""

from __future__ import annotations

from models.routes import LeisureTag, PoiPoint
from search.yandex.client import geocode_city, get_api_key, search_organizations
from search.yandex.leisure_tags import leisure_pool_limit, search_text_for_tag
from search.yandex.parse import feature_to_poi


def _rank_key(poi: PoiPoint) -> tuple[float, float]:
    rating = poi.rating if poi.rating is not None else 0.0
    return (rating, 1.0 if poi.address else 0.0)


def search_leisure_points(
    *,
    city: str,
    categories: list[LeisureTag],
    pace: str = "moderate",
) -> list[PoiPoint]:
    geo = geocode_city(city)
    if geo is None:
        return []
    lon, lat, (spn_lon, spn_lat) = geo
    limit = leisure_pool_limit(pace)
    seen_ids: set[str] = set()
    collected: list[PoiPoint] = []

    for tag in categories:
        if len(collected) >= limit:
            break
        text = search_text_for_tag(tag, city)
        if get_api_key():
            features = search_organizations(
                text=text,
                lon=lon,
                lat=lat,
                spn_lon=spn_lon,
                spn_lat=spn_lat,
                results=min(15, limit),
            )
        else:
            features = _fallback_features(city, tag, lon, lat, index=len(collected))
        for feature in features:
            poi = feature_to_poi(feature, tag=tag)
            if poi is None or poi.poi_id in seen_ids:
                continue
            seen_ids.add(poi.poi_id)
            collected.append(poi)
            if len(collected) >= limit:
                break

    collected.sort(key=_rank_key, reverse=True)
    return collected[:limit]


def _fallback_features(
    city: str,
    tag: LeisureTag,
    lon: float,
    lat: float,
    *,
    index: int,
) -> list[dict]:
    """Демо-POI без API-ключа (для dev и тестов)."""
    from search.yandex.leisure_tags import TAG_SPECS

    label = TAG_SPECS[tag].label_ru
    name = f"{label} {city} #{index + 1}"
    oid = abs(hash(f"{city}_{tag}_{index}")) % 10_000_000_000
    url = f"https://yandex.ru/maps/org/demo_{tag}/{oid}"
    offset = index * 0.004
    return [
        {
            "geometry": {"coordinates": [lon + offset, lat + offset * 0.5]},
            "properties": {
                "CompanyMetaData": {
                    "name": name,
                    "url": url,
                    "address": city,
                    "rating": {"value": 4.5 - index * 0.1},
                }
            },
        }
    ]
