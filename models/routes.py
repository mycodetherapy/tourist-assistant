"""Контракты маршрутов: пул POI и 3 варианта на всю поездку."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

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

_DEFAULT_CASE_TITLES: dict[str, str] = {
    "A": "Лёгкая прогулка",
    "B": "Средний маршрут",
    "C": "Длинный маршрут",
    "N-A": "Лёгкая прогулка",
    "N-B": "Средний маршрут",
    "N-C": "Длинный маршрут",
}


def _first_non_empty_str(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        val = data.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def normalize_trip_route_case(raw: Any) -> Any:
    """Приводит типичные алиасы LLM (route_id, route_title, …) к контракту TripRouteCase."""
    if not isinstance(raw, dict):
        return raw
    data = dict(raw)
    case_id = _first_non_empty_str(data, "case_id", "route_id", "variant_id", "id")
    if case_id:
        data["case_id"] = case_id
    title = _first_non_empty_str(data, "title", "route_title", "route_name", "name")
    if title:
        data["title"] = title
    elif case_id:
        data["title"] = _DEFAULT_CASE_TITLES.get(case_id, f"Маршрут {case_id}")
    data["summary"] = _first_non_empty_str(
        data,
        "summary",
        "route_summary",
        "route_description",
        "description",
    )
    return data


def normalize_route_program_payload(raw: Any) -> Any:
    if isinstance(raw, list):
        return {"cases": [normalize_trip_route_case(item) for item in raw]}
    if not isinstance(raw, dict):
        return raw
    data = dict(raw)
    cases = data.get("cases")
    if cases is None and isinstance(data.get("routes"), list):
        cases = data.pop("routes")
        data["cases"] = cases
    if isinstance(cases, list):
        data["cases"] = [normalize_trip_route_case(item) for item in cases]
    return data


def normalize_routes_draft_payload(raw: Any) -> Any:
    if not isinstance(raw, dict):
        return raw
    data = dict(raw)
    if "routes" in data:
        data["routes"] = normalize_route_program_payload(data["routes"])
    return data


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


class RouteGeometry(BaseModel):
    type: Literal["LineString"] = "LineString"
    coordinates: list[list[float]] = Field(
        default_factory=list,
        description="GeoJSON: [[lon, lat], ...]",
    )


class TripRouteCase(BaseModel):
    case_id: RouteCaseId
    title: str
    summary: str
    stops: list[RouteStop] = Field(default_factory=list)
    maps_route_url: str = ""
    loop_route: bool = False
    preserved: bool = False
    route_geometry: RouteGeometry | None = None
    route_distance_m: float | None = None
    route_duration_s: float | None = None
    route_map_anchor: GeoPoint | None = Field(
        default=None,
        description="Базовая точка на карте (без номера); задаётся при сборке maps_route_url",
    )
    route_map_leisure_coords: list[GeoPoint] = Field(
        default_factory=list,
        description="Координаты leisure-остановок для нумерации на карте",
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_aliases(cls, data: Any) -> Any:
        return normalize_trip_route_case(data)


class RouteProgram(BaseModel):
    schema_version: Literal[1] = 1
    materials_summary: str = ""
    cases: list[TripRouteCase] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_payload(cls, data: Any) -> Any:
        return normalize_route_program_payload(data)
