"""graph_runs persistence (Postgres)."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from sqlalchemy import select, update

from db.models.schema import GraphRun
from db.postgres._helpers import iso_dt, utc_now
from db.session import pg_session

GraphRunStatus = Literal["queued", "running", "completed", "failed"]
CityFactStatus = Literal["pending", "ready", "failed", "skipped", "idle"]


def create_graph_run(
    *,
    user_id: int,
    trip_id: int,
    scope: str,
    city_fact_status: CityFactStatus = "idle",
) -> uuid.UUID:
    run_id = uuid.uuid4()
    with pg_session() as session:
        row = GraphRun(
            id=run_id,
            user_id=user_id,
            trip_id=trip_id,
            scope=scope,
            status="queued",
            city_fact_status=city_fact_status,
            created_at=utc_now(),
        )
        session.add(row)
        session.flush()
        return run_id


def get_graph_run(run_id: uuid.UUID) -> dict[str, Any] | None:
    with pg_session() as session:
        row = session.get(GraphRun, run_id)
        if row is None:
            return None
        return _row_to_dict(row)


def update_graph_run(run_id: uuid.UUID, **fields: Any) -> None:
    if not fields:
        return
    with pg_session() as session:
        session.execute(
            update(GraphRun).where(GraphRun.id == run_id).values(**fields)
        )


def has_active_graph_run(trip_id: int) -> bool:
    with pg_session() as session:
        row = session.execute(
            select(GraphRun.id)
            .where(
                GraphRun.trip_id == trip_id,
                GraphRun.status.in_(("queued", "running")),
            )
            .limit(1)
        ).first()
    return row is not None


def acquire_trip_build_lock(trip_id: int, *, ttl_sec: int = 3600) -> bool:
    from db.redis_client import get_redis

    client = get_redis()
    key = f"trip:{trip_id}:build_lock"
    return bool(client.set(key, "1", nx=True, ex=ttl_sec))


def release_trip_build_lock(trip_id: int) -> None:
    from db.redis_client import get_redis

    get_redis().delete(f"trip:{trip_id}:build_lock")


def _row_to_dict(row: GraphRun) -> dict[str, Any]:
    return {
        "run_id": str(row.id),
        "trip_id": int(row.trip_id),
        "user_id": int(row.user_id),
        "scope": row.scope,
        "status": row.status,
        "error": row.error,
        "version_id": int(row.version_id) if row.version_id is not None else None,
        "graph_run_id": row.graph_run_id,
        "city_fact_status": row.city_fact_status,
        "worker_id": row.worker_id,
        "created_at": iso_dt(row.created_at),
        "started_at": iso_dt(row.started_at) if row.started_at else None,
        "finished_at": iso_dt(row.finished_at) if row.finished_at else None,
    }
