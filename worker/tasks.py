"""RQ worker tasks (LangGraph + city fact)."""

from __future__ import annotations

import os
import uuid
from typing import Any

from agents.llm_context import LlmConfig, run_with_llm_config
from db.postgres import graph_runs as pg_runs
from db.postgres._helpers import utc_now
from db.session import is_postgres_enabled
from search.context import search_context_scope
from services.errors import format_runtime_error
from services.trip_service import TripService


def _require_pg() -> None:
    if not is_postgres_enabled():
        raise RuntimeError("worker requires DATABASE_URL")


def _llm_config_for_user(user_id: int) -> LlmConfig:
    from api.auth.service import AuthError, require_user_llm_config

    try:
        return require_user_llm_config(user_id)
    except AuthError as exc:
        raise RuntimeError(str(exc)) from exc


def build_routes_task(graph_run_id: str, payload: dict[str, Any]) -> None:
    """RQ: полный прогон графа для поездки."""
    _require_pg()
    run_uuid = uuid.UUID(graph_run_id)
    trip_id = int(payload["trip_id"])
    user_id = int(payload["user_id"])
    scope = str(payload.get("scope") or "full")
    worker_id = os.getenv("HOSTNAME", "worker")

    pg_runs.update_graph_run(
        run_uuid,
        status="running",
        started_at=utc_now(),
        worker_id=worker_id,
    )
    pg_runs.release_trip_build_lock(trip_id)

    service = TripService()

    try:
        llm_config = _llm_config_for_user(user_id)
        state = service.prepare_continue_trip(trip_id, scope)
        with search_context_scope():
            with run_with_llm_config(llm_config):
                result = service.run_graph(state, graph_run_id=graph_run_id)
        version_id = result.version_id
        pg_runs.update_graph_run(
            run_uuid,
            status="completed",
            version_id=version_id,
            graph_run_id=result.run_id,
            finished_at=utc_now(),
            city_fact_status="pending" if scope == "full" else "skipped",
        )
        if scope == "full" and version_id is not None:
            from services.job_enqueue import enqueue_city_fact

            enqueue_city_fact(
                graph_run_id=run_uuid,
                payload={
                    "trip_id": trip_id,
                    "user_id": user_id,
                    "version_id": version_id,
                    "city": str(state.get("city") or ""),
                },
            )
    except Exception as exc:
        pg_runs.update_graph_run(
            run_uuid,
            status="failed",
            error=format_runtime_error(exc),
            finished_at=utc_now(),
            city_fact_status="failed" if scope == "full" else "skipped",
        )
        raise


def city_fact_task(graph_run_id: str, payload: dict[str, Any]) -> None:
    """RQ: async факт о городе."""
    _require_pg()
    from agents.city_fact import generate_city_fact
    from db.repository import patch_itinerary_program

    run_uuid = uuid.UUID(graph_run_id)
    user_id = int(payload["user_id"])
    version_id = int(payload["version_id"])
    city = str(payload["city"])
    try:
        llm_config = _llm_config_for_user(user_id)
        with run_with_llm_config(llm_config):
            fact = generate_city_fact(city=city, use_llm=True)
        patch_itinerary_program(
            version_id,
            {"lifehacks": fact, "city_fact_status": "ready"},
        )
        pg_runs.update_graph_run(run_uuid, city_fact_status="ready")
    except Exception:
        patch_itinerary_program(version_id, {"city_fact_status": "failed"})
        pg_runs.update_graph_run(run_uuid, city_fact_status="failed")
        raise
