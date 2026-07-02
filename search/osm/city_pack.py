"""City pack: готовность, пути, lazy prepare."""

from __future__ import annotations

import json
import logging
import sqlite3
import subprocess
import uuid
from pathlib import Path

from config.city_catalog import (
    CityPackSpec,
    city_pack_dir,
    get_city_pack_spec,
    resolve_city_slug,
)

logger = logging.getLogger(__name__)

_PREPARE_IN_FLIGHT: set[str] = set()


def pack_dir_for_slug(slug: str) -> Path:
    return city_pack_dir(slug)


def _poi_count(db_path: Path) -> int:
    if not db_path.is_file():
        return 0
    try:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute("SELECT COUNT(*) FROM poi").fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()
    except sqlite3.Error:
        return 0


def is_pack_ready(slug: str) -> bool:
    spec = get_city_pack_spec(slug)
    if spec is None:
        custom = pack_dir_for_slug(slug)
        if not custom.is_dir():
            return False
        poi_db = custom / "poi.sqlite"
        meta = custom / "meta.json"
        return poi_db.is_file() and meta.is_file()
    if not spec.poi_db_path.is_file():
        return False
    return spec.meta_path.is_file()


def pack_poi_count(slug: str) -> int:
    spec = get_city_pack_spec(slug)
    db_path = spec.poi_db_path if spec else pack_dir_for_slug(slug) / "poi.sqlite"
    return _poi_count(db_path)


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
    """Ставит lazy-prepare в очередь для городов каталога. Возвращает slug."""
    slug = resolve_city_slug(city)
    if not slug:
        return None
    if is_pack_ready(slug):
        return slug
    if slug in _PREPARE_IN_FLIGHT:
        return slug
    _PREPARE_IN_FLIGHT.add(slug)
    try:
        from db.postgres.city_packs import upsert_city_pack_status

        upsert_city_pack_status(slug, status="queued")
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
    try:
        from db.postgres.city_packs import upsert_city_pack_status

        upsert_city_pack_status(slug, status="building")
    except Exception as exc:
        logger.warning("city_packs status building failed: %s", exc)

    try:
        if get_city_pack_spec(slug) is not None:
            subprocess.run(
                ["bash", str(root / "scripts" / "city_pack_prepare.sh"), slug],
                check=True,
                cwd=str(root),
            )
        else:
            display = city or slug
            fo_id = __import__("os").getenv("LAZY_PACK_FO", "volga")
            subprocess.run(
                [
                    sys.executable,
                    str(root / "scripts" / "city_pack_prepare_lazy_impl.py"),
                    slug,
                    display,
                    fo_id,
                ],
                check=True,
                cwd=str(root),
            )
        try:
            from db.postgres.city_packs import mark_city_pack_ready

            mark_city_pack_ready(slug)
        except Exception as exc:
            logger.warning("city_packs mark ready failed: %s", exc)
    except Exception:
        try:
            from db.postgres.city_packs import upsert_city_pack_status

            upsert_city_pack_status(slug, status="failed", error_message="prepare failed")
        except Exception as exc:
            logger.warning("city_packs status failed: %s", exc)
        raise
    finally:
        _PREPARE_IN_FLIGHT.discard(slug)


__all__ = [
    "ensure_pack_async",
    "is_pack_ready",
    "pack_poi_count",
    "read_pack_meta",
    "resolve_city_slug",
    "resolve_pack_for_city",
    "run_pack_prepare_subprocess",
]
