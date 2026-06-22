"""PostgreSQL CRUD (dual-backend with db/repository.py facade)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.constants import BOOTSTRAP_USER_ID
from db.models.schema import (
    AgentRun,
    ItineraryVersion,
    ProgramItemFeedback,
    SectionArtifact,
    ToolRun,
    Trip,
    TripPreferences,
    UserProfile,
)
from db.postgres._helpers import iso_dt, utc_now
from db.session import pg_session
from db.types import PlannedTripSummary, TripSummary


def create_trip(
    city: str,
    dates: str,
    origin_city: str,
    user_query: str,
    *,
    user_id: int = BOOTSTRAP_USER_ID,
) -> int:
    now = utc_now()
    with pg_session() as session:
        trip = Trip(
            user_id=user_id,
            city=city,
            dates=dates,
            origin_city=origin_city,
            user_query=user_query,
            status="active",
            created_at=now,
            updated_at=now,
        )
        session.add(trip)
        session.flush()
        return int(trip.id)


def delete_trip(trip_id: int, *, user_id: int | None = None) -> bool:
    with pg_session() as session:
        stmt = delete(Trip).where(Trip.id == trip_id)
        if user_id is not None:
            stmt = stmt.where(Trip.user_id == user_id)
        result = session.execute(stmt)
        return (result.rowcount or 0) > 0


def save_preferences(trip_id: int, preferences: dict[str, Any]) -> None:
    with pg_session() as session:
        stmt = pg_insert(TripPreferences).values(
            trip_id=trip_id,
            preferences_json=preferences,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[TripPreferences.trip_id],
            set_={"preferences_json": preferences},
        )
        session.execute(stmt)


def get_preferences(trip_id: int) -> dict[str, Any] | None:
    with pg_session() as session:
        row = session.get(TripPreferences, trip_id)
        if row is None:
            return None
        return dict(row.preferences_json)


def _get_profile_from_table(user_id: int) -> dict[str, Any] | None:
    with pg_session() as session:
        row = session.get(UserProfile, user_id)
        if row is None:
            return None
        return dict(row.preferences_json)


def get_latest_trip_preferences(user_id: int = BOOTSTRAP_USER_ID) -> dict[str, Any] | None:
    with pg_session() as session:
        row = session.execute(
            select(TripPreferences.preferences_json)
            .join(Trip, Trip.id == TripPreferences.trip_id)
            .where(Trip.user_id == user_id)
            .order_by(Trip.updated_at.desc())
            .limit(1)
        ).first()
    if row is None:
        return None
    return dict(row[0])


def has_user_profile(user_id: int = BOOTSTRAP_USER_ID) -> bool:
    return get_user_profile(user_id) is not None


def get_user_profile(user_id: int = BOOTSTRAP_USER_ID) -> dict[str, Any] | None:
    profile = _get_profile_from_table(user_id)
    if profile is not None:
        return profile
    return get_latest_trip_preferences(user_id)


def ensure_user_profile_from_trips(user_id: int = BOOTSTRAP_USER_ID) -> None:
    if _get_profile_from_table(user_id) is not None:
        return
    latest = get_latest_trip_preferences(user_id)
    if latest is not None:
        save_user_profile(latest, user_id=user_id)


def save_user_profile(
    preferences: dict[str, Any],
    *,
    user_id: int = BOOTSTRAP_USER_ID,
) -> None:
    now = utc_now()
    with pg_session() as session:
        stmt = pg_insert(UserProfile).values(
            user_id=user_id,
            preferences_json=preferences,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[UserProfile.user_id],
            set_={"preferences_json": preferences, "updated_at": now},
        )
        session.execute(stmt)


def list_planned_trips(limit: int = 20) -> list[PlannedTripSummary]:
    latest_sq = (
        select(
            ItineraryVersion.trip_id,
            func.max(ItineraryVersion.version).label("max_version"),
        )
        .group_by(ItineraryVersion.trip_id)
        .subquery()
    )
    with pg_session() as session:
        rows = session.execute(
            select(
                Trip.id,
                Trip.city,
                Trip.dates,
                Trip.origin_city,
                Trip.updated_at,
                ItineraryVersion.version,
                ItineraryVersion.scope,
            )
            .join(ItineraryVersion, ItineraryVersion.trip_id == Trip.id)
            .join(
                latest_sq,
                (latest_sq.c.trip_id == Trip.id)
                & (ItineraryVersion.version == latest_sq.c.max_version),
            )
            .order_by(Trip.updated_at.desc())
            .limit(limit)
        ).all()
    return [
        PlannedTripSummary(
            id=int(r.id),
            city=r.city,
            dates=r.dates,
            origin_city=r.origin_city,
            updated_at=iso_dt(r.updated_at),
            last_version=int(r.version),
            last_scope=r.scope,
        )
        for r in rows
    ]


def list_trips(limit: int = 20, *, user_id: int | None = None) -> list[TripSummary]:
    with pg_session() as session:
        stmt = select(
            Trip.id,
            Trip.city,
            Trip.dates,
            Trip.origin_city,
            Trip.updated_at,
        ).order_by(Trip.updated_at.desc()).limit(limit)
        if user_id is not None:
            stmt = stmt.where(Trip.user_id == user_id)
        rows = session.execute(stmt).all()
    return [
        TripSummary(
            id=int(r.id),
            city=r.city,
            dates=r.dates,
            origin_city=r.origin_city,
            updated_at=iso_dt(r.updated_at),
        )
        for r in rows
    ]


def get_trip(trip_id: int, *, user_id: int | None = None) -> dict[str, Any] | None:
    with pg_session() as session:
        trip = session.get(Trip, trip_id)
        if trip is None:
            return None
        if user_id is not None and int(trip.user_id) != user_id:
            return None
        return {
            "id": int(trip.id),
            "user_id": int(trip.user_id),
            "city": trip.city,
            "dates": trip.dates,
            "origin_city": trip.origin_city,
            "user_query": trip.user_query,
            "created_at": iso_dt(trip.created_at),
            "updated_at": iso_dt(trip.updated_at),
        }


def trip_belongs_to_user(trip_id: int, user_id: int) -> bool:
    return get_trip(trip_id, user_id=user_id) is not None


def next_version_number(trip_id: int) -> int:
    with pg_session() as session:
        max_v = session.execute(
            select(func.coalesce(func.max(ItineraryVersion.version), 0)).where(
                ItineraryVersion.trip_id == trip_id
            )
        ).scalar_one()
    return int(max_v) + 1


def list_item_feedback_pairs(trip_id: int) -> list[tuple[str, str]]:
    with pg_session() as session:
        rows = session.execute(
            select(ProgramItemFeedback.section, ProgramItemFeedback.item_key).where(
                ProgramItemFeedback.trip_id == trip_id
            )
        ).all()
    return [(r.section, r.item_key) for r in rows]


def prune_stale_item_feedback(
    trip_id: int,
    program: dict[str, Any],
    scope: str,
    *,
    reset_route_stops: bool = False,
) -> int:
    from program.feedback_prune import find_stale_feedback_keys

    existing = list_item_feedback_pairs(trip_id)
    route_stop_votes = list_item_feedback_by_section(trip_id, "route_stops")
    stale = find_stale_feedback_keys(
        program,
        scope,
        existing=existing,
        trip_id=trip_id,
        route_stop_votes=route_stop_votes,
        reset_route_stops=reset_route_stops,
    )
    for section, item_key in stale:
        delete_item_feedback(trip_id, section, item_key)
    return len(stale)


def save_itinerary_version(
    trip_id: int,
    program: dict[str, Any],
    *,
    scope: str = "full",
    approved: bool = False,
) -> int:
    reset_stops = scope in ("routes", "full", "events", "dining")
    prune_stale_item_feedback(
        trip_id, program, scope, reset_route_stops=reset_stops
    )
    version = next_version_number(trip_id)
    now = utc_now()
    with pg_session() as session:
        row = ItineraryVersion(
            trip_id=trip_id,
            version=version,
            scope=scope,
            program_json=program,
            approved=approved,
            created_at=now,
        )
        session.add(row)
        session.execute(
            update(Trip).where(Trip.id == trip_id).values(updated_at=now)
        )
        session.flush()
        return int(row.id)


def log_tool_run(
    trip_id: int,
    tool_name: str,
    *,
    args: dict[str, Any] | None = None,
    provider: str | None = None,
    live_data: bool = False,
    results_count: int = 0,
    raw_results_count: int = 0,
    error: str | None = None,
    itinerary_version_id: int | None = None,
) -> int:
    now = utc_now()
    with pg_session() as session:
        row = ToolRun(
            trip_id=trip_id,
            itinerary_version_id=itinerary_version_id,
            tool_name=tool_name,
            args_json=json.dumps(args or {}, ensure_ascii=False),
            provider=provider,
            live_data=live_data,
            results_count=results_count,
            raw_results_count=raw_results_count,
            error=error,
            created_at=now,
        )
        session.add(row)
        session.flush()
        return int(row.id)


def log_agent_run(
    trip_id: int,
    *,
    run_id: str,
    rebuild_scope: str,
    duration_ms: int,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    total_cost_usd: float | None = None,
    node_timings: dict[str, Any] | None = None,
) -> int:
    now = utc_now()
    with pg_session() as session:
        row = AgentRun(
            trip_id=trip_id,
            run_id=run_id,
            rebuild_scope=rebuild_scope,
            duration_ms=int(duration_ms),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            total_cost_usd=total_cost_usd,
            node_timings_json=node_timings,
            created_at=now,
        )
        session.add(row)
        session.flush()
        return int(row.id)


def list_agent_runs(trip_id: int | None = None, limit: int = 50) -> list[dict[str, Any]]:
    with pg_session() as session:
        stmt = select(AgentRun).order_by(AgentRun.id.desc()).limit(limit)
        if trip_id is not None:
            stmt = stmt.where(AgentRun.trip_id == trip_id)
        rows = session.scalars(stmt).all()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "trip_id": int(row.trip_id),
                "run_id": row.run_id,
                "rebuild_scope": row.rebuild_scope,
                "duration_ms": int(row.duration_ms),
                "prompt_tokens": row.prompt_tokens,
                "completion_tokens": row.completion_tokens,
                "total_tokens": row.total_tokens,
                "total_cost_usd": row.total_cost_usd,
                "node_timings": row.node_timings_json,
                "created_at": iso_dt(row.created_at),
            }
        )
    return out


def list_tool_runs(trip_id: int, limit: int = 50) -> list[dict[str, Any]]:
    with pg_session() as session:
        rows = session.scalars(
            select(ToolRun)
            .where(ToolRun.trip_id == trip_id)
            .order_by(ToolRun.id.desc())
            .limit(limit)
        ).all()
    return [
        {
            "tool_name": r.tool_name,
            "provider": r.provider,
            "live_data": r.live_data,
            "results_count": r.results_count,
            "raw_results_count": r.raw_results_count,
            "error": r.error,
            "created_at": iso_dt(r.created_at),
        }
        for r in rows
    ]


def mark_latest_itinerary_approved(trip_id: int) -> None:
    with pg_session() as session:
        latest = session.execute(
            select(ItineraryVersion.id)
            .where(ItineraryVersion.trip_id == trip_id)
            .order_by(ItineraryVersion.version.desc())
            .limit(1)
        ).scalar_one_or_none()
        if latest is None:
            return
        session.execute(
            update(ItineraryVersion)
            .where(ItineraryVersion.id == latest)
            .values(approved=True)
        )


def list_trip_itinerary_programs(
    trip_id: int,
    *,
    limit: int = 30,
) -> list[dict[str, Any]]:
    with pg_session() as session:
        rows = session.scalars(
            select(ItineraryVersion)
            .where(ItineraryVersion.trip_id == trip_id)
            .order_by(ItineraryVersion.version.desc())
            .limit(limit)
        ).all()
    programs: list[dict[str, Any]] = []
    for row in rows:
        data = row.program_json
        if isinstance(data, dict):
            programs.append(data)
    return programs


def get_latest_itinerary(trip_id: int) -> dict[str, Any] | None:
    with pg_session() as session:
        row = session.scalars(
            select(ItineraryVersion)
            .where(ItineraryVersion.trip_id == trip_id)
            .order_by(ItineraryVersion.version.desc())
            .limit(1)
        ).first()
    if row is None:
        return None
    return {
        "id": int(row.id),
        "version": int(row.version),
        "scope": row.scope,
        "program": dict(row.program_json),
        "approved": bool(row.approved),
        "created_at": iso_dt(row.created_at),
    }


def get_itinerary_version(trip_id: int, version_id: int) -> dict[str, Any] | None:
    with pg_session() as session:
        row = session.get(ItineraryVersion, version_id)
    if row is None or int(row.trip_id) != trip_id:
        return None
    return {
        "id": int(row.id),
        "trip_id": int(row.trip_id),
        "version": int(row.version),
        "scope": row.scope,
        "program": dict(row.program_json),
        "approved": bool(row.approved),
        "created_at": iso_dt(row.created_at),
    }


def patch_itinerary_program(version_id: int, patch: dict[str, Any]) -> bool:
    if not patch:
        return False
    now = utc_now()
    with pg_session() as session:
        row = session.get(ItineraryVersion, version_id)
        if row is None:
            return False
        program = dict(row.program_json) if isinstance(row.program_json, dict) else {}
        program.update(patch)
        row.program_json = program
        session.execute(
            update(Trip).where(Trip.id == row.trip_id).values(updated_at=now)
        )
    return True


def list_item_feedback(trip_id: int) -> dict[str, int]:
    with pg_session() as session:
        rows = session.scalars(
            select(ProgramItemFeedback)
            .where(ProgramItemFeedback.trip_id == trip_id)
            .order_by(ProgramItemFeedback.updated_at.asc(), ProgramItemFeedback.id.asc())
        ).all()
    return {r.item_key: int(r.vote) for r in rows}


def list_item_feedback_by_section(trip_id: int, section: str) -> dict[str, int]:
    with pg_session() as session:
        rows = session.scalars(
            select(ProgramItemFeedback)
            .where(
                ProgramItemFeedback.trip_id == trip_id,
                ProgramItemFeedback.section == section,
            )
            .order_by(ProgramItemFeedback.updated_at.asc(), ProgramItemFeedback.id.asc())
        ).all()
    return {r.item_key: int(r.vote) for r in rows}


def list_item_feedback_by_index(trip_id: int) -> dict[tuple[str, int], int]:
    with pg_session() as session:
        rows = session.scalars(
            select(ProgramItemFeedback)
            .where(ProgramItemFeedback.trip_id == trip_id)
            .order_by(ProgramItemFeedback.updated_at.asc(), ProgramItemFeedback.id.asc())
        ).all()
    return {(r.section, int(r.item_index)): int(r.vote) for r in rows}


def upsert_item_feedback(
    trip_id: int,
    itinerary_version_id: int | None,
    section: str,
    item_index: int,
    item_key: str,
    vote: int,
) -> None:
    now = utc_now()
    with pg_session() as session:
        stmt = pg_insert(ProgramItemFeedback).values(
            trip_id=trip_id,
            itinerary_version_id=itinerary_version_id,
            section=section,
            item_index=item_index,
            item_key=item_key,
            vote=vote,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                ProgramItemFeedback.trip_id,
                ProgramItemFeedback.section,
                ProgramItemFeedback.item_key,
            ],
            set_={
                "vote": vote,
                "item_index": item_index,
                "itinerary_version_id": itinerary_version_id,
                "updated_at": now,
            },
        )
        session.execute(stmt)


def delete_item_feedback(trip_id: int, section: str, item_key: str) -> None:
    with pg_session() as session:
        session.execute(
            delete(ProgramItemFeedback).where(
                ProgramItemFeedback.trip_id == trip_id,
                ProgramItemFeedback.section == section,
                ProgramItemFeedback.item_key == item_key,
            )
        )


def delete_feedback_at_index(
    trip_id: int,
    section: str,
    item_index: int,
    *,
    except_item_key: str | None = None,
) -> int:
    with pg_session() as session:
        stmt = delete(ProgramItemFeedback).where(
            ProgramItemFeedback.trip_id == trip_id,
            ProgramItemFeedback.section == section,
            ProgramItemFeedback.item_index == item_index,
        )
        if except_item_key:
            stmt = stmt.where(ProgramItemFeedback.item_key != except_item_key)
        result = session.execute(stmt)
        return int(result.rowcount or 0)


def save_section_artifact(
    trip_id: int,
    section: str,
    payload: dict[str, Any],
    *,
    digest: str | None = None,
) -> None:
    now = utc_now()
    with pg_session() as session:
        stmt = pg_insert(SectionArtifact).values(
            trip_id=trip_id,
            section=section,
            digest=digest,
            payload_json=payload,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[SectionArtifact.trip_id, SectionArtifact.section],
            set_={
                "digest": digest,
                "payload_json": payload,
                "updated_at": now,
            },
        )
        session.execute(stmt)


def get_section_artifact(trip_id: int, section: str) -> dict[str, Any] | None:
    with pg_session() as session:
        row = session.get(SectionArtifact, (trip_id, section))
        if row is None:
            return None
        payload = row.payload_json if isinstance(row.payload_json, dict) else {}
        return {"digest": row.digest, "payload": payload}
