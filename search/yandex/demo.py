"""Признаки демо-POI (когда Geocoder не вернул места)."""

from __future__ import annotations

from models.routes import DiningOption, PoiPoint


def is_demo_poi(poi: PoiPoint) -> bool:
    return "/org/demo_" in poi.maps_url


def is_demo_dining(option: DiningOption) -> bool:
    return "/org/demo_" in option.maps_url


def has_real_leisure(points: list[PoiPoint]) -> bool:
    return any(not is_demo_poi(p) for p in points)
