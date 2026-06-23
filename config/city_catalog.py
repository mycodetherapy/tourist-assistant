"""Загрузка config/city_packs.yaml и config/federal_districts.yaml."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parent.parent
_FO_PATH = Path(__file__).resolve().parent / "federal_districts.yaml"
_PACKS_PATH = Path(__file__).resolve().parent / "city_packs.yaml"


def project_root() -> Path:
    return _ROOT


def data_root() -> Path:
    return Path(
        __import__("os").getenv("TOURIST_DATA_DIR", str(_ROOT / "data"))
    ).resolve()


def fo_data_dir() -> Path:
    return data_root() / "fo"


def city_pack_dir(slug: str) -> Path:
    return data_root() / "cities" / slug


@dataclass(frozen=True)
class FederalDistrict:
    id: str
    pbf_name: str
    geofabrik_url: str
    min_pbf_bytes: int

    @property
    def pbf_path(self) -> Path:
        return fo_data_dir() / self.pbf_name


@dataclass(frozen=True)
class CityPackSpec:
    slug: str
    display_name: str
    federal_district: str
    names: tuple[str, ...]
    poi_radius_km: float
    routing_buffer_km: float
    compose_profile: str
    osrm_service: str
    is_default: bool = True

    @property
    def pack_dir(self) -> Path:
        return city_pack_dir(self.slug)

    @property
    def poi_db_path(self) -> Path:
        return self.pack_dir / "poi.sqlite"

    @property
    def extract_pbf_path(self) -> Path:
        return self.pack_dir / "extract.osm.pbf"

    @property
    def osrm_dir(self) -> Path:
        return self.pack_dir / "osrm"

    @property
    def meta_path(self) -> Path:
        return self.pack_dir / "meta.json"

    @property
    def osrm_base_name(self) -> str:
        return self.slug


def _normalize_city_name(city: str) -> str:
    return re.sub(r"\s+", " ", (city or "").strip().lower())


@lru_cache(maxsize=1)
def load_federal_districts() -> dict[str, FederalDistrict]:
    raw = yaml.safe_load(_FO_PATH.read_text(encoding="utf-8")) or {}
    out: dict[str, FederalDistrict] = {}
    for district_id, item in (raw.get("districts") or {}).items():
        if not isinstance(item, dict):
            continue
        out[str(district_id)] = FederalDistrict(
            id=str(district_id),
            pbf_name=str(item["pbf_name"]),
            geofabrik_url=str(item["geofabrik_url"]),
            min_pbf_bytes=int(item.get("min_pbf_bytes", 50 * 1024 * 1024)),
        )
    return out


@lru_cache(maxsize=1)
def load_city_pack_specs() -> dict[str, CityPackSpec]:
    raw = yaml.safe_load(_PACKS_PATH.read_text(encoding="utf-8")) or {}
    out: dict[str, CityPackSpec] = {}
    for item in raw.get("default_packs") or []:
        if not isinstance(item, dict):
            continue
        slug = str(item["slug"])
        names = tuple(str(n) for n in item.get("names") or [])
        out[slug] = CityPackSpec(
            slug=slug,
            display_name=str(item.get("display_name") or slug),
            federal_district=str(item["federal_district"]),
            names=names,
            poi_radius_km=float(item.get("poi_radius_km", 4.5)),
            routing_buffer_km=float(item.get("routing_buffer_km", 1.0)),
            compose_profile=str(item.get("compose_profile") or f"routing-city-{slug}"),
            osrm_service=str(item.get("osrm_service") or f"osrm-{slug}"),
            is_default=True,
        )
    return out


def resolve_city_slug(city: str) -> str | None:
    key = _normalize_city_name(city)
    if not key:
        return None
    for spec in load_city_pack_specs().values():
        for name in spec.names:
            if _normalize_city_name(name) == key:
                return spec.slug
    return None


def get_city_pack_spec(slug: str) -> CityPackSpec | None:
    return load_city_pack_specs().get(slug)


def get_federal_district(district_id: str) -> FederalDistrict | None:
    return load_federal_districts().get(district_id)


def default_pack_slugs() -> list[str]:
    return list(load_city_pack_specs().keys())


def is_default_pack(slug: str) -> bool:
    spec = get_city_pack_spec(slug)
    return spec is not None and spec.is_default
