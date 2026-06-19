"""Фоновые прогоны графа: in-memory (SQLite) или RQ + graph_runs (Postgres)."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from typing import Literal

from agents.llm_context import LlmConfig, run_with_llm_config
from db.repository import get_trip
from db.session import is_postgres_enabled
from models.state import AgentState
from search.context import bootstrap_from_agent_state, clear_search_context
from services.city_fact_job import schedule_city_fact_generation
from services.errors import format_runtime_error
from services.run_quotas import check_and_consume_run_quota
from services.saas_events import audit
from services.trip_service import GraphRunResult, TripService

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


def _use_job_queue() -> bool:
    from db.redis_client import is_redis_enabled

    return is_postgres_enabled() and is_redis_enabled()


class RunManager:
    """Запускает граф в фоне: потоки (SQLite) или RQ worker (Postgres)."""

    def __init__(self, trip_service: TripService | None = None) -> None:
        self._service = trip_service or TripService()
        self._runs: dict[str, RunRecord] = {}
        self._lock = threading.Lock()

    def get(self, run_id: str) -> RunRecord | None:
        if _use_job_queue():
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
        with self._lock:
            return self._runs.get(run_id)

    def forget_runs_for_trip(self, trip_id: int) -> None:
        """Убирает записи прогонов поездки из памяти (после удаления из БД)."""
        if _use_job_queue():
            return
        with self._lock:
            for run_id in [
                rid
                for rid, record in self._runs.items()
                if record.trip_id == trip_id
            ]:
                del self._runs[run_id]

    def has_active_run_for_trip(self, trip_id: int) -> bool:
        """Есть ли незавершённый прогон для поездки."""
        if _use_job_queue():
            from db.postgres import graph_runs as pg_runs

            return pg_runs.has_active_graph_run(trip_id)
        with self._lock:
            return any(
                record.trip_id == trip_id and record.status in ("queued", "running")
                for record in self._runs.values()
            )

    def start_run(self, state: AgentState, *, llm_config: LlmConfig) -> str:
        """Ставит прогон в очередь и возвращает run_id для polling."""
        trip_id = int(state["trip_id"])
        scope = str(state.get("rebuild_scope", "full"))
        trip = get_trip(trip_id)
        if trip is None:
            raise ValueError(f"Поездка #{trip_id} не найдена")
        user_id = int(trip["user_id"])
        check_and_consume_run_quota(user_id=user_id, scope=scope)
        audit(
            action="graph_run.start",
            entity_type="trip",
            entity_id=str(trip_id),
            user_id=user_id,
            metadata={"scope": scope},
        )
        if _use_job_queue():
            return self._start_run_queue(trip_id, scope)
        return self._start_run_thread(state, trip_id, scope, llm_config)

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

    def _start_run_thread(
        self,
        state: AgentState,
        trip_id: int,
        scope: str,
        llm_config: LlmConfig,
    ) -> str:
        run_id = str(uuid.uuid4())
        record = RunRecord(run_id=run_id, trip_id=trip_id, scope=scope, status="queued")
        if scope == "full":
            record.city_fact_status = "pending"
        else:
            record.city_fact_status = "skipped"
        with self._lock:
            self._runs[run_id] = record

        thread = threading.Thread(
            target=self._execute,
            args=(run_id, state, llm_config),
            daemon=True,
        )
        thread.start()
        return run_id

    def _execute(self, run_id: str, state: AgentState, llm_config: LlmConfig) -> None:
        bootstrap_from_agent_state(state)
        try:
            self._execute_graph(run_id, state, llm_config)
        finally:
            clear_search_context()

    def _execute_graph(
        self, run_id: str, state: AgentState, llm_config: LlmConfig
    ) -> None:
        with self._lock:
            record = self._runs[run_id]
            record.status = "running"

        scope = str(state.get("rebuild_scope", "full"))
        city = str(state.get("city", ""))
        trip_id = int(state["trip_id"])
        version_event = threading.Event()
        version_holder: dict[str, int | None] = {"version_id": None}

        if scope == "full":
            schedule_city_fact_generation(
                trip_id=trip_id,
                city=city,
                version_id=None,
                llm_config=llm_config,
                version_event=version_event,
                version_holder=version_holder,
            )

        try:
            with run_with_llm_config(llm_config):
                result: GraphRunResult = self._service.run_graph(state)
            version_holder["version_id"] = result.version_id
            version_event.set()
            with self._lock:
                record = self._runs[run_id]
                record.status = "completed"
                record.version_id = result.version_id
                record.graph_run_id = result.run_id
                if scope == "full":
                    record.city_fact_status = "pending"
        except Exception as exc:
            version_event.set()
            with self._lock:
                record = self._runs[run_id]
                record.status = "failed"
                record.error = format_runtime_error(exc)
                if scope == "full":
                    record.city_fact_status = "failed"
