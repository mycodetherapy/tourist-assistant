"""Фоновые прогоны графа через Redis + graph_runs (Postgres)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from auth.service import resolve_run_context
from db.repository import get_trip
from db.session import is_postgres_enabled
from models.state import AgentState
from services.errors import format_runtime_error
from services.free_run_quotas import check_and_consume_free_run_quota
from services.run_quotas import check_and_consume_run_quota
from services.saas_events import audit
from services.trip_service import TripService

RunStatusName = Literal["queued", "running", "completed", "failed"]
CityFactStatusName = Literal["pending", "ready", "failed", "skipped", "idle"]


@dataclass
class RunRecord:
    """Статус одного фонового прогона."""

    run_id: str
    trip_id: int
    scope: str
    status: RunStatusName = "queued"
    error: str | None = None
    version_id: int | None = None
    graph_run_id: str | None = None
    city_fact_status: CityFactStatusName = "idle"


def _require_queue() -> None:
    from db.redis_client import is_redis_enabled

    if not is_postgres_enabled():
        raise RuntimeError("DATABASE_URL is required")
    if not is_redis_enabled():
        raise RuntimeError("REDIS_URL is required for graph runs")


class RunManager:
    """Ставит прогоны графа в Redis-очередь worker."""

    def __init__(self, trip_service: TripService | None = None) -> None:
        self._service = trip_service or TripService()

    def get(self, run_id: str) -> RunRecord | None:
        _require_queue()
        from db.postgres import graph_runs as pg_runs

        row = pg_runs.get_graph_run(uuid.UUID(run_id))
        if row is None:
            return None
        return RunRecord(
            run_id=row["run_id"],
            trip_id=int(row["trip_id"]),
            scope=str(row["scope"]),
            status=row["status"],
            error=row.get("error"),
            version_id=row.get("version_id"),
            graph_run_id=row.get("graph_run_id"),
            city_fact_status=row.get("city_fact_status") or "idle",
        )

    def forget_runs_for_trip(self, trip_id: int) -> None:
        """No-op: статусы хранятся в Postgres."""

    def has_active_run_for_trip(self, trip_id: int) -> bool:
        _require_queue()
        from db.postgres import graph_runs as pg_runs

        return pg_runs.has_active_graph_run(trip_id)

    def start_run(self, state: AgentState, *, llm_config: LlmConfig) -> str:
        """Ставит прогон в очередь и возвращает run_id для polling."""
        _require_queue()
        trip_id = int(state["trip_id"])
        scope = str(state.get("rebuild_scope", "full"))
        trip = get_trip(trip_id)
        if trip is None:
            raise ValueError(f"Поездка #{trip_id} не найдена")
        user_id = int(trip["user_id"])
        run_ctx = resolve_run_context(user_id)
        if run_ctx.mode == "none":
            check_and_consume_free_run_quota(user_id=user_id)
        else:
            check_and_consume_run_quota(user_id=user_id, scope=scope)
        audit(
            action="graph_run.start",
            entity_type="trip",
            entity_id=str(trip_id),
            user_id=user_id,
            metadata={"scope": scope},
        )
        return self._start_run_queue(trip_id, scope)

    def _start_run_queue(self, trip_id: int, scope: str) -> str:
        from db.postgres import graph_runs as pg_runs
        from services.job_enqueue import enqueue_build_routes

        trip = get_trip(trip_id)
        if trip is None:
            raise ValueError(f"Поездка #{trip_id} не найдена")
        pg_runs.fail_stale_graph_runs(trip_id)
        if pg_runs.has_active_graph_run(trip_id):
            raise ValueError("Для поездки уже выполняется сборка маршрута")
        if not pg_runs.acquire_trip_build_lock(trip_id):
            raise ValueError("Для поездки уже выполняется сборка маршрута")

        city_fact_status: CityFactStatusName = (
            "pending" if scope == "full" else "skipped"
        )
        run_uuid = pg_runs.create_graph_run(
            user_id=int(trip["user_id"]),
            trip_id=trip_id,
            scope=scope,
            city_fact_status=city_fact_status,
        )
        payload = {
            "trip_id": trip_id,
            "user_id": int(trip["user_id"]),
            "scope": scope,
        }
        try:
            enqueue_build_routes(graph_run_id=run_uuid, payload=payload)
        except Exception as exc:
            pg_runs.release_trip_build_lock(trip_id)
            pg_runs.update_graph_run(
                run_uuid,
                status="failed",
                error=format_runtime_error(exc),
            )
            raise
        return str(run_uuid)
