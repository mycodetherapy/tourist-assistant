"""Сборка маршрутов без LLM (free tier)."""

from __future__ import annotations

import json
import uuid
from time import perf_counter
from typing import Any

from agents.finalize_helpers import repair_program_routes, resolve_routes_program
from db import get_trip, log_agent_run, save_itinerary_version
from models.schemas import FinalProgram, normalize_stored_program
from models.state import AgentState
from planning.rebuild import merge_program
from search.context import clear_route_materials
from search.tools import TOOL_MAP
from services.trip_service import GraphRunResult


def _collect_tool_warnings(content: str) -> list[str]:
    text = (content or "").strip()
    if not text or text.startswith("Ошибка"):
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    warnings: list[str] = []
    raw_warnings = data.get("warnings")
    if isinstance(raw_warnings, list):
        warnings.extend(str(item).strip() for item in raw_warnings if str(item).strip())
    raw_warning = data.get("warning")
    if raw_warning and str(raw_warning).strip():
        item = str(raw_warning).strip()
        if item not in warnings:
            warnings.append(item)
    return warnings


def _invoke_route_materials(*, city: str, dates: str) -> str:
    clear_route_materials()
    return TOOL_MAP["search_route_materials"].invoke({"city": city, "dates": dates})


def run_deterministic_build(
    state: AgentState,
    *,
    graph_run_id: str | None = None,
) -> GraphRunResult:
    """Algorithmic pipeline: materials tool → fallback routes → save program."""
    trip_id = int(state["trip_id"])
    rebuild_scope = str(state.get("rebuild_scope", "full"))
    city = str(state.get("city") or "")
    dates = str(state.get("dates") or "")
    base_program = state.get("base_program")
    prefs = state.get("preferences") or {}
    transport = str(prefs.get("transport_preference") or "mixed")
    pace = str(prefs.get("pace") or "moderate")
    feedback_snapshot = state.get("route_feedback_snapshot")

    data_warnings = list(state.get("data_warnings") or [])
    messages: list[Any] = list(state.get("messages") or [])

    started = perf_counter()
    if rebuild_scope == "full":
        tool_content = _invoke_route_materials(city=city, dates=dates)
        if trip_id is not None and not str(tool_content).startswith("Ошибка"):
            from search.route_materials_store import persist_route_materials_from_tool

            persist_route_materials_from_tool(trip_id, tool_content)
        for warning in _collect_tool_warnings(tool_content):
            if warning not in data_warnings:
                data_warnings.append(warning)

    routes_program, routes_text = resolve_routes_program(
        messages,
        None,
        base_program=base_program,
        transport=transport,
        pace=pace,
        expected_city=city,
        trip_id=trip_id,
        dates=dates,
        rebuild_scope=rebuild_scope,
        route_feedback_snapshot=feedback_snapshot,
    )

    draft_fields: dict[str, Any] = {
        "routes": routes_program.model_dump(),
        "routes_text": routes_text,
        "lifehacks": "",
        "tickets": "",
    }
    if rebuild_scope == "full":
        draft_fields["city_fact_status"] = "pending"
    elif rebuild_scope == "routes" and base_program:
        draft_fields["lifehacks"] = str(base_program.get("lifehacks") or "")
        draft_fields["city_fact_status"] = str(
            base_program.get("city_fact_status") or "ready"
        )
    else:
        draft_fields["city_fact_status"] = "skipped"

    merged = merge_program(base_program, draft_fields, rebuild_scope)
    if rebuild_scope == "full":
        merged["lifehacks"] = ""
        merged["city_fact_status"] = "pending"
    if data_warnings:
        merged["data_warnings"] = data_warnings

    merged = repair_program_routes(
        merged,
        messages=messages,
        trip_id=trip_id,
        city=city,
        dates=dates,
        base_program=base_program,
        transport=transport,
        pace=pace,
    )
    program = FinalProgram.model_validate(normalize_stored_program(merged))
    program_dump = dict(merged)
    program_dump.update(program.model_dump())

    version_id = save_itinerary_version(
        trip_id,
        program_dump,
        scope=rebuild_scope,
        approved=False,
    )

    duration_ms = int((perf_counter() - started) * 1000)
    run_id = str(uuid.uuid4())
    log_agent_run(
        trip_id,
        run_id=run_id,
        rebuild_scope=rebuild_scope,
        duration_ms=duration_ms,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        total_cost_usd=0.0,
        node_timings={"deterministic": duration_ms},
    )

    trip = get_trip(trip_id)
    if trip is not None:
        from services.saas_events import usage_from_graph_run

        usage_from_graph_run(
            user_id=int(trip["user_id"]),
            trip_id=trip_id,
            scope=rebuild_scope,
            graph_run_id=graph_run_id,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_usd=0.0,
        )

    result_state: AgentState = {
        **state,
        "program": program_dump,
        "data_warnings": data_warnings,
        "critic_passed": True,
    }
    return GraphRunResult(state=result_state, run_id=run_id, version_id=version_id)
