"""city_packs catalog persistence (Postgres)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from config.city_catalog import city_pack_dir, get_city_pack_spec, load_city_pack_specs
from db.models.schema import CityPack
from db.postgres._helpers import utc_now
from db.session import is_postgres_enabled, pg_session
from search.osm.city_pack import is_pack_ready, pack_poi_count


def _storage_path(slug: str) -> str:
    return str(city_pack_dir(slug))


def sync_city_pack_catalog() -> None:
    """Синхронизирует записи каталога из city_packs.yaml."""
    if not is_postgres_enabled():
        return
    now = utc_now()
    with pg_session() as session:
        for spec in load_city_pack_specs().values():
            ready = is_pack_ready(spec.slug)
            stmt = (
                insert(CityPack)
                .values(
                    slug=spec.slug,
                    display_name=spec.display_name,
                    federal_district=spec.federal_district,
                    status="ready" if ready else "queued",
                    poi_count=pack_poi_count(spec.slug) if ready else None,
                    storage_path=_storage_path(spec.slug),
                    prepared_at=now if ready else None,
                    updated_at=now,
                )
                .on_conflict_do_update(
                    index_elements=[CityPack.slug],
                    set_={
                        "display_name": spec.display_name,
                        "federal_district": spec.federal_district,
                        "storage_path": _storage_path(spec.slug),
                        "updated_at": now,
                    },
                )
            )
            session.execute(stmt)


def upsert_city_pack_status(
    slug: str,
    *,
    status: str,
    error_message: str | None = None,
) -> None:
    if not is_postgres_enabled():
        return
    spec = get_city_pack_spec(slug)
    display_name = spec.display_name if spec else slug
    federal_district = spec.federal_district if spec else "volga"
    now = utc_now()
    with pg_session() as session:
        stmt = (
            insert(CityPack)
            .values(
                slug=slug,
                display_name=display_name,
                federal_district=federal_district,
                status=status,
                storage_path=_storage_path(slug),
                error_message=error_message,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=[CityPack.slug],
                set_={
                    "status": status,
                    "error_message": error_message,
                    "updated_at": now,
                },
            )
        )
        session.execute(stmt)


def mark_city_pack_ready(slug: str) -> None:
    if not is_postgres_enabled():
        return
    now = utc_now()
    count = pack_poi_count(slug)
    with pg_session() as session:
        row = session.get(CityPack, slug)
        if row is None:
            spec = get_city_pack_spec(slug)
            row = CityPack(
                slug=slug,
                display_name=spec.display_name if spec else slug,
                federal_district=spec.federal_district if spec else "volga",
                status="ready",
                poi_count=count,
                storage_path=_storage_path(slug),
                prepared_at=now,
                updated_at=now,
            )
            session.add(row)
            return
        row.status = "ready"
        row.poi_count = count
        row.prepared_at = now
        row.error_message = None
        row.updated_at = now


def get_city_pack_status(slug: str) -> dict[str, Any] | None:
    if not is_postgres_enabled():
        return None
    with pg_session() as session:
        row = session.get(CityPack, slug)
        if row is None:
            return None
        return {
            "slug": row.slug,
            "display_name": row.display_name,
            "federal_district": row.federal_district,
            "status": row.status,
            "poi_count": row.poi_count,
            "storage_path": row.storage_path,
            "error_message": row.error_message,
            "prepared_at": row.prepared_at.isoformat() if row.prepared_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }


def list_city_packs() -> list[dict[str, Any]]:
    if not is_postgres_enabled():
        return []
    with pg_session() as session:
        rows = session.scalars(select(CityPack).order_by(CityPack.display_name)).all()
        return [
            {
                "slug": row.slug,
                "display_name": row.display_name,
                "federal_district": row.federal_district,
                "status": row.status,
                "poi_count": row.poi_count,
                "storage_path": row.storage_path,
                "error_message": row.error_message,
                "prepared_at": row.prepared_at.isoformat() if row.prepared_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in rows
        ]
