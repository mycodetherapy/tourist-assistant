"""Worker tasks (LangGraph + city fact)."""

from __future__ import annotations

import os
import uuid
from typing import Any

from agents.llm_context import LlmConfig, run_with_llm_config
from auth.service import resolve_run_context
from db.postgres import graph_runs as pg_runs
from db.postgres._helpers import utc_now
from db.session import is_postgres_enabled
from search.context import search_context_scope, set_poi_source_policy
from services.deterministic_runner import run_deterministic_build
from services.errors import format_runtime_error
from services.trip_service import TripService


def _require_pg() -> None:
    if not is_postgres_enabled():
        raise RuntimeError("worker requires DATABASE_URL")


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
        run_ctx = resolve_run_context(user_id)
        state = service.prepare_continue_trip(trip_id, scope)
        with search_context_scope(state):
            set_poi_source_policy(use_city_pack=run_ctx.mode != "none")
            if run_ctx.mode == "none":
                result = run_deterministic_build(state, graph_run_id=graph_run_id)
            else:
                assert run_ctx.llm_config is not None
                with run_with_llm_config(run_ctx.llm_config):
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
                    "use_llm": run_ctx.mode != "none",
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
    use_llm = bool(payload.get("use_llm", True))
    try:
        if use_llm:
            run_ctx = resolve_run_context(user_id)
            assert run_ctx.llm_config is not None
            with run_with_llm_config(run_ctx.llm_config):
                fact = generate_city_fact(city=city, use_llm=True)
        else:
            fact = generate_city_fact(city=city, use_llm=False)
        patch_itinerary_program(
            version_id,
            {"lifehacks": fact, "city_fact_status": "ready"},
        )
        pg_runs.update_graph_run(run_uuid, city_fact_status="ready")
    except Exception:
        patch_itinerary_program(version_id, {"city_fact_status": "failed"})
        pg_runs.update_graph_run(run_uuid, city_fact_status="failed")
        raise


def poi_fact_task(job_id: str, payload: dict[str, Any]) -> None:
    """Async справка по POI (on-demand, глобальный кэш poi_facts)."""
    _require_pg()
    from agents.poi_fact import POI_FACT_NOT_FOUND, generate_poi_fact, looks_like_city_article
    from db.postgres import poi_facts as pg_poi_facts
    from search.poi_fact_sources import resolve_poi_context

    user_id = int(payload["user_id"])
    trip_id = int(payload["trip_id"])
    city = str(payload["city"])
    cache_key = str(payload["cache_key"])
    poi_id = str(payload.get("poi_id") or "")
    name = str(payload.get("name") or "")

    try:
        use_llm = resolve_run_context(user_id).mode == "byok"
        ctx = resolve_poi_context(
            trip_id=trip_id,
            city=city,
            poi_id=poi_id or None,
            name=name,
        )
        if use_llm:
            run_ctx = resolve_run_context(user_id)
            assert run_ctx.llm_config is not None
            with run_with_llm_config(run_ctx.llm_config):
                result = generate_poi_fact(ctx, use_llm=True)
        else:
            result = generate_poi_fact(ctx, use_llm=False)
        if not ctx.wikidata_qid and looks_like_city_article(result.text):
            raise RuntimeError(POI_FACT_NOT_FOUND)
        pg_poi_facts.mark_poi_fact_ready(
            cache_key=cache_key,
            text=result.text,
            used_llm=result.used_llm,
            source_kind=result.source_kind,
        )
    except Exception as exc:
        from services.errors import format_runtime_error

        pg_poi_facts.mark_poi_fact_failed(
            cache_key=cache_key,
            error=format_runtime_error(exc),
        )
        raise


def prepare_city_pack_task(graph_run_id: str, payload: dict[str, Any]) -> None:
    """RQ: lazy подготовка city pack для города вне default_packs."""
    from search.osm.city_pack import run_pack_prepare_subprocess

    slug = str(payload.get("slug") or "")
    city = str(payload.get("city") or slug)
    if not slug:
        raise ValueError("prepare_city_pack: slug required")
    run_pack_prepare_subprocess(slug, city=city)


def prepare_osrm_task(graph_run_id: str, payload: dict[str, Any]) -> None:
    """Self-serve / user-initiated OSRM prepare (FO → extract → osrm)."""
    from search.osrm.prepare_job import prepare_osrm_task as _run

    _run(graph_run_id, payload)
