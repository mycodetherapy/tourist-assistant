"""City pack: готовность, пути, lazy prepare."""

from __future__ import annotations

import json
import logging
import subprocess
import uuid
from pathlib import Path

from config.city_catalog import (
    CityPackSpec,
    city_pack_dir,
    get_city_pack_spec,
    is_default_pack,
    resolve_city_slug,
)

logger = logging.getLogger(__name__)

_PREPARE_IN_FLIGHT: set[str] = set()


def pack_dir_for_slug(slug: str) -> Path:
    return city_pack_dir(slug)


def is_pack_ready(slug: str) -> bool:
    spec = get_city_pack_spec(slug)
    if spec is None:
        custom = pack_dir_for_slug(slug)
        if not custom.is_dir():
            return False
        poi_db = custom / "poi.sqlite"
        meta = custom / "meta.json"
        osrm_dir = custom / "osrm"
        osrm_files = list(osrm_dir.glob("*.osrm.mldgr")) if osrm_dir.is_dir() else []
        return poi_db.is_file() and meta.is_file() and bool(osrm_files)
    if not spec.poi_db_path.is_file():
        return False
    if not spec.meta_path.is_file():
        return False
    osrm_mldgr = spec.osrm_dir / f"{spec.osrm_base_name}.osrm.mldgr"
    return osrm_mldgr.is_file()


def read_pack_meta(slug: str) -> dict | None:
    spec = get_city_pack_spec(slug)
    meta_path = spec.meta_path if spec else pack_dir_for_slug(slug) / "meta.json"
    if not meta_path.is_file():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def resolve_pack_for_city(city: str) -> tuple[str | None, CityPackSpec | None]:
    slug = resolve_city_slug(city)
    if slug is None:
        return None, None
    return slug, get_city_pack_spec(slug)


def ensure_pack_async(city: str) -> str | None:
    """Ставит lazy-prepare в очередь для городов вне default_packs. Возвращает slug."""
    slug = resolve_city_slug(city)
    if not slug:
        slug = _slugify_city(city)
    if is_pack_ready(slug):
        return slug
    if is_default_pack(slug):
        logger.warning("default pack %s not ready — run city_pack_prepare.sh", slug)
        return slug
    if slug in _PREPARE_IN_FLIGHT:
        return slug
    _PREPARE_IN_FLIGHT.add(slug)
    try:
        from services.job_enqueue import enqueue_prepare_city_pack

        enqueue_prepare_city_pack(slug=slug, city=city)
    except Exception as exc:
        logger.warning("enqueue prepare_city_pack failed: %s", exc)
        _PREPARE_IN_FLIGHT.discard(slug)
    return slug


def run_pack_prepare_subprocess(slug: str, *, city: str = "") -> None:
    """Синхронная подготовка pack (worker task)."""
    import sys

    root = Path(__file__).resolve().parents[2]
    if get_city_pack_spec(slug) is not None:
        subprocess.run(
            ["bash", str(root / "scripts" / "city_pack_prepare.sh"), slug],
            check=True,
            cwd=str(root),
        )
        return
    display = city or slug
    fo_id = __import__("os").getenv("LAZY_PACK_FO", "volga")
    subprocess.run(
        [sys.executable, str(root / "scripts" / "city_pack_prepare_lazy_impl.py"), slug, display, fo_id],
        check=True,
        cwd=str(root),
    )


def _slugify_city(city: str) -> str:
    import re

    key = re.sub(r"[^a-z0-9]+", "-", city.strip().lower())
    return key.strip("-") or f"city-{uuid.uuid4().hex[:8]}"


__all__ = [
    "ensure_pack_async",
    "is_pack_ready",
    "read_pack_meta",
    "resolve_city_slug",
    "resolve_pack_for_city",
    "run_pack_prepare_subprocess",
]
