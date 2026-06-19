"""RQ job failure hooks → graph_runs status."""

from __future__ import annotations

import uuid
from typing import Any

from db.postgres._helpers import utc_now
from db.session import is_postgres_enabled
from services.errors import format_runtime_error


def on_graph_job_failure(
    job: Any,
    connection: Any,
    exc_type: type[BaseException],
    exc_value: BaseException,
    traceback: str,
) -> None:
    """Синхронизирует graph_runs при падении RQ (fork crash, timeout)."""
    if not is_postgres_enabled() or not job.args:
        return
    try:
        run_uuid = uuid.UUID(str(job.args[0]))
    except (ValueError, TypeError):
        return
    from db.postgres import graph_runs as pg_runs

    trip_id = None
    if len(job.args) > 1 and isinstance(job.args[1], dict):
        raw = job.args[1].get("trip_id")
        if raw is not None:
            trip_id = int(raw)
    pg_runs.update_graph_run(
        run_uuid,
        status="failed",
        error=format_runtime_error(exc_value),
        finished_at=utc_now(),
    )
    if trip_id is not None:
        pg_runs.release_trip_build_lock(trip_id)
