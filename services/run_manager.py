"""Фоновые прогоны графа для API с in-memory статусами."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from typing import Literal

from agents.llm_context import LlmConfig, run_with_llm_config
from models.state import AgentState
from services.city_fact_job import schedule_city_fact_generation
from services.errors import format_runtime_error
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


class RunManager:
    """Запускает граф в фоне; статусы хранятся в памяти процесса API."""

    def __init__(self, trip_service: TripService | None = None) -> None:
        self._service = trip_service or TripService()
        self._runs: dict[str, RunRecord] = {}
        self._lock = threading.Lock()

    def get(self, run_id: str) -> RunRecord | None:
        with self._lock:
            return self._runs.get(run_id)

    def forget_runs_for_trip(self, trip_id: int) -> None:
        """Убирает записи прогонов поездки из памяти (после удаления из БД)."""
        with self._lock:
            for run_id in [
                rid
                for rid, record in self._runs.items()
                if record.trip_id == trip_id
            ]:
                del self._runs[run_id]

    def has_active_run_for_trip(self, trip_id: int) -> bool:
        """Есть ли незавершённый прогон для поездки в памяти процесса."""
        with self._lock:
            return any(
                record.trip_id == trip_id and record.status in ("queued", "running")
                for record in self._runs.values()
            )

    def start_run(self, state: AgentState, *, llm_config: LlmConfig) -> str:
        """Ставит прогон в очередь и возвращает run_id для polling."""
        run_id = str(uuid.uuid4())
        trip_id = int(state["trip_id"])
        scope = str(state.get("rebuild_scope", "full"))
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
