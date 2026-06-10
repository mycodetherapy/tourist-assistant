"""Контракты маршрутов: пул POI и 3 варианта на всю поездку."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

LeisureTag = Literal[
    "landmarks",
    "parks",
    "museums",
    "embankments",
    "monuments",
    "temples",
    "pedestrian_streets",
    # legacy (старые поездки в SQLite)
    "exhibitions",
    "galleries",
    "philharmonic",
    "theaters",
]

RouteCaseId = str
NEW_ROUTE_BATCH_IDS = ("N-A", "N-B", "N-C")


class GeoPoint(BaseModel):
    lon: float
    lat: float


class PoiPoint(BaseModel):
    poi_id: str
    tag: LeisureTag
    name: str
    coordinates: GeoPoint
    maps_url: str
    rating: float | None = None
    address: str = ""


class DiningOption(BaseModel):
    poi_id: str
    anchor_poi_id: str
    name: str
    coordinates: GeoPoint
    maps_url: str
    rating: float | None = None


class RouteMaterialsInput(BaseModel):
    city: str = Field(..., description="Город пребывания")
    dates: str = Field(..., description="Даты поездки")


class RouteMaterials(BaseModel):
    schema_version: Literal[1] = 1
    provider: Literal["osm", "yandex_maps", "fallback"] = "osm"
    city: str
    dates: str
    leisure_points: list[PoiPoint] = Field(default_factory=list)
    dining_options: list[DiningOption] = Field(default_factory=list)


class RouteStop(BaseModel):
    order: int
    kind: Literal["leisure", "dining", "transit_note"]
    poi_id: str | None = None
    time_hint: str = ""
    narrative: str = ""


class TripRouteCase(BaseModel):
    case_id: RouteCaseId
    title: str
    summary: str
    stops: list[RouteStop] = Field(default_factory=list)
    maps_route_url: str = ""
    loop_route: bool = False
    preserved: bool = False


class RouteProgram(BaseModel):
    schema_version: Literal[1] = 1
    materials_summary: str = ""
    cases: list[TripRouteCase] = Field(default_factory=list)
