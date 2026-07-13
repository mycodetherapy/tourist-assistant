"""CRUD для глобального кэша poi_facts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.models.schema import PoiFact
from db.postgres._helpers import utc_now
from db.session import pg_session

PoiFactStatus = Literal["pending", "ready", "failed"]

_PENDING_STALE_MINUTES = 3


def _row_to_dict(row: PoiFact) -> dict[str, Any]:
    return {
        "cache_key": row.cache_key,
        "poi_name": row.poi_name,
        "city": row.city,
        "status": row.status,
        "text": row.text,
        "source_kind": row.source_kind,
        "used_llm": bool(row.used_llm),
        "error": row.error,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def get_poi_fact(cache_key: str) -> dict[str, Any] | None:
    with pg_session() as session:
        row = session.get(PoiFact, cache_key)
        return _row_to_dict(row) if row else None


def is_pending_stale(updated_at: datetime | None) -> bool:
    if updated_at is None:
        return True
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return updated_at < utc_now() - timedelta(minutes=_PENDING_STALE_MINUTES)


def upsert_poi_fact_pending(
    *,
    cache_key: str,
    poi_name: str,
    city: str,
    source_kind: str,
) -> dict[str, Any]:
    now = utc_now()
    with pg_session() as session:
        stmt = (
            pg_insert(PoiFact)
            .values(
                cache_key=cache_key,
                poi_name=poi_name,
                city=city,
                status="pending",
                text=None,
                source_kind=source_kind,
                used_llm=False,
                error=None,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=[PoiFact.cache_key],
                set_={
                    "poi_name": poi_name,
                    "city": city,
                    "status": "pending",
                    "text": None,
                    "source_kind": source_kind,
                    "used_llm": False,
                    "error": None,
                    "updated_at": now,
                },
            )
        )
        session.execute(stmt)
        row = session.get(PoiFact, cache_key)
        assert row is not None
        return _row_to_dict(row)


def mark_poi_fact_ready(
    *,
    cache_key: str,
    text: str,
    used_llm: bool,
    source_kind: str,
) -> None:
    now = utc_now()
    with pg_session() as session:
        session.query(PoiFact).filter(PoiFact.cache_key == cache_key).update(
            {
                PoiFact.status: "ready",
                PoiFact.text: text,
                PoiFact.used_llm: used_llm,
                PoiFact.source_kind: source_kind,
                PoiFact.error: None,
                PoiFact.updated_at: now,
            }
        )


def mark_poi_fact_failed(*, cache_key: str, error: str) -> None:
    now = utc_now()
    with pg_session() as session:
        session.query(PoiFact).filter(PoiFact.cache_key == cache_key).update(
            {
                PoiFact.status: "failed",
                PoiFact.error: error[:2000],
                PoiFact.updated_at: now,
            }
        )
