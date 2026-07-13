"""RQ job failure hooks → graph_runs status."""

from __future__ import annotations

import uuid
from typing import Any

from db.postgres._helpers import utc_now
from db.session import is_postgres_enabled
from services.errors import format_runtime_error


def _payload(job: Any) -> dict[str, Any]:
    if len(job.args) > 1 and isinstance(job.args[1], dict):
        return job.args[1]
    return {}


def on_graph_job_failure(
    job: Any,
    connection: Any,
    exc_type: type[BaseException],
    exc_value: BaseException,
    traceback: str,
) -> None:
    """Синхронизирует graph_runs и program при падении RQ (fork crash, timeout)."""
    if not is_postgres_enabled() or not job.args:
        return
    try:
        run_uuid = uuid.UUID(str(job.args[0]))
    except (ValueError, TypeError):
        return

    from db.postgres import graph_runs as pg_runs

    payload = _payload(job)
    trip_id_raw = payload.get("trip_id")
    trip_id = int(trip_id_raw) if trip_id_raw is not None else None
    error = format_runtime_error(exc_value)
    is_city_fact = "city_fact_task" in str(getattr(job, "func_name", "") or "")

    if is_city_fact:
        version_id = payload.get("version_id")
        if version_id is not None:
            from db.repository import patch_itinerary_program

            patch_itinerary_program(int(version_id), {"city_fact_status": "failed"})
        pg_runs.update_graph_run(run_uuid, city_fact_status="failed")
        return

    pg_runs.update_graph_run(
        run_uuid,
        status="failed",
        error=error,
        finished_at=utc_now(),
        city_fact_status="failed",
    )
    if trip_id is not None:
        pg_runs.release_trip_build_lock(trip_id)


def on_json_job_failure(
    *,
    task: str,
    graph_run_id: str,
    payload: dict[str, Any],
    exc: BaseException,
) -> None:
    """Синхронизирует graph_runs при падении JSON worker loop."""
    if not is_postgres_enabled():
        return
    try:
        run_uuid = uuid.UUID(str(graph_run_id))
    except (ValueError, TypeError):
        return

    from db.postgres import graph_runs as pg_runs

    error = format_runtime_error(exc)
    trip_id_raw = payload.get("trip_id")
    trip_id = int(trip_id_raw) if trip_id_raw is not None else None

    if task == "city_fact":
        version_id = payload.get("version_id")
        if version_id is not None:
            from db.repository import patch_itinerary_program

            patch_itinerary_program(int(version_id), {"city_fact_status": "failed"})
        pg_runs.update_graph_run(run_uuid, city_fact_status="failed")
        return

    if task == "poi_fact":
        cache_key = str(payload.get("cache_key") or "")
        if cache_key:
            from db.postgres import poi_facts as pg_poi_facts

            pg_poi_facts.mark_poi_fact_failed(
                cache_key=cache_key,
                error=error,
            )
        return

    pg_runs.update_graph_run(
        run_uuid,
        status="failed",
        error=error,
        finished_at=utc_now(),
        city_fact_status="failed",
    )
    if trip_id is not None:
        pg_runs.release_trip_build_lock(trip_id)
