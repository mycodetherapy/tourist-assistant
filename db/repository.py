"""CRUD для поездок, предпочтений и версий программы."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from db.connection import connect


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class TripSummary:
    """Краткая информация о поездке для списка в CLI."""

    id: int
    city: str
    dates: str
    origin_city: str
    status: str
    updated_at: str


@dataclass(frozen=True)
class PlannedTripSummary:
    """Поездка с сохранённой программой (для просмотра подробностей)."""

    id: int
    city: str
    dates: str
    origin_city: str
    status: str
    updated_at: str
    last_version: int
    last_scope: str


def create_trip(
    city: str,
    dates: str,
    origin_city: str,
    user_query: str,
    *,
    status: str = "draft",
) -> int:
    """Создаёт запись поездки и возвращает trip_id."""
    now = _utc_now()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO trips (city, dates, origin_city, user_query, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (city, dates, origin_city, user_query, status, now, now),
        )
        conn.commit()
        return int(cursor.lastrowid)


def delete_trip(trip_id: int) -> bool:
    """Удаляет поездку и связанные записи (CASCADE). Возвращает True, если запись была."""
    with connect() as conn:
        cursor = conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
        conn.commit()
        return cursor.rowcount > 0


def update_trip_status(trip_id: int, status: str) -> None:
    """Обновляет статус поездки и updated_at."""
    with connect() as conn:
        conn.execute(
            "UPDATE trips SET status = ?, updated_at = ? WHERE id = ?",
            (status, _utc_now(), trip_id),
        )
        conn.commit()


def save_preferences(trip_id: int, preferences: dict[str, Any]) -> None:
    """Сохраняет JSON предпочтений опросника (upsert)."""
    payload = json.dumps(preferences, ensure_ascii=False)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO trip_preferences (trip_id, preferences_json)
            VALUES (?, ?)
            ON CONFLICT(trip_id) DO UPDATE SET preferences_json = excluded.preferences_json
            """,
            (trip_id, payload),
        )
        conn.commit()


def get_preferences(trip_id: int) -> dict[str, Any] | None:
    """Загружает предпочтения поездки или None."""
    with connect() as conn:
        row = conn.execute(
            "SELECT preferences_json FROM trip_preferences WHERE trip_id = ?",
            (trip_id,),
        ).fetchone()
    if row is None:
        return None
    return json.loads(row["preferences_json"])


def _get_profile_from_table() -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT preferences_json FROM user_profile WHERE id = 1",
        ).fetchone()
    if row is None:
        return None
    return json.loads(row["preferences_json"])


def get_latest_trip_preferences() -> dict[str, Any] | None:
    """
    Предпочтения последней поездки — fallback, если user_profile ещё пуст
    (например, прогон оборвался до save_user_profile).
    """
    with connect() as conn:
        row = conn.execute(
            """
            SELECT tp.preferences_json
            FROM trip_preferences tp
            INNER JOIN trips t ON t.id = tp.trip_id
            ORDER BY t.updated_at DESC
            LIMIT 1
            """,
        ).fetchone()
    if row is None:
        return None
    return json.loads(row["preferences_json"])


def has_user_profile() -> bool:
    """True, если опросник уже проходили (профиль или любая поездка с prefs)."""
    return get_user_profile() is not None


def get_user_profile() -> dict[str, Any] | None:
    """Предпочтения: сначала user_profile, иначе последняя поездка с опросником."""
    profile = _get_profile_from_table()
    if profile is not None:
        return profile
    return get_latest_trip_preferences()


def ensure_user_profile_from_trips() -> None:
    """Копирует prefs последней поездки в user_profile, если профиль пуст."""
    if _get_profile_from_table() is not None:
        return
    latest = get_latest_trip_preferences()
    if latest is not None:
        save_user_profile(latest)


def save_user_profile(preferences: dict[str, Any]) -> None:
    """Обновляет глобальный профиль предпочтений (id=1)."""
    payload = json.dumps(preferences, ensure_ascii=False)
    now = _utc_now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO user_profile (id, preferences_json, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                preferences_json = excluded.preferences_json,
                updated_at = excluded.updated_at
            """,
            (payload, now),
        )
        conn.commit()


def list_planned_trips(limit: int = 20) -> list[PlannedTripSummary]:
    """Поездки с хотя бы одной сохранённой версией программы."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                t.id,
                t.city,
                t.dates,
                t.origin_city,
                t.status,
                t.updated_at,
                iv.version AS last_version,
                iv.scope AS last_scope
            FROM trips t
            INNER JOIN itinerary_versions iv ON iv.trip_id = t.id
            INNER JOIN (
                SELECT trip_id, MAX(version) AS max_version
                FROM itinerary_versions
                GROUP BY trip_id
            ) latest ON latest.trip_id = t.id AND iv.version = latest.max_version
            ORDER BY t.updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        PlannedTripSummary(
            id=int(r["id"]),
            city=r["city"],
            dates=r["dates"],
            origin_city=r["origin_city"],
            status=r["status"],
            updated_at=r["updated_at"],
            last_version=int(r["last_version"]),
            last_scope=r["last_scope"],
        )
        for r in rows
    ]


def list_trips(limit: int = 20) -> list[TripSummary]:
    """Список поездок, новые сверху."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, city, dates, origin_city, status, updated_at
            FROM trips
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        TripSummary(
            id=int(r["id"]),
            city=r["city"],
            dates=r["dates"],
            origin_city=r["origin_city"],
            status=r["status"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]


def get_trip(trip_id: int) -> dict[str, Any] | None:
    """Возвращает поля поездки или None."""
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, city, dates, origin_city, user_query, status, created_at, updated_at
            FROM trips WHERE id = ?
            """,
            (trip_id,),
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def next_version_number(trip_id: int) -> int:
    """Следующий номер версии программы для поездки."""
    with connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(version), 0) AS max_v FROM itinerary_versions WHERE trip_id = ?",
            (trip_id,),
        ).fetchone()
    return int(row["max_v"]) + 1


def list_item_feedback_pairs(trip_id: int) -> list[tuple[str, str]]:
    """Все оценки поездки: [(section, item_key), ...]."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT section, item_key
            FROM program_item_feedback
            WHERE trip_id = ?
            """,
            (trip_id,),
        ).fetchall()
    return [(row["section"], row["item_key"]) for row in rows]


def prune_stale_item_feedback(
    trip_id: int,
    program: dict[str, Any],
    scope: str,
    *,
    reset_route_stops: bool = False,
) -> int:
    """Удаляет оценки пересобранных пунктов; возвращает число удалённых."""
    from program.feedback_prune import find_stale_feedback_keys

    existing = list_item_feedback_pairs(trip_id)
    stale = find_stale_feedback_keys(
        program,
        scope,
        existing=existing,
        trip_id=trip_id,
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
    """Сохраняет версию программы; возвращает id записи itinerary_versions."""
    reset_stops = scope in ("routes", "full", "events", "dining")
    prune_stale_item_feedback(
        trip_id, program, scope, reset_route_stops=reset_stops
    )
    version = next_version_number(trip_id)
    now = _utc_now()
    program_json = json.dumps(program, ensure_ascii=False)
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO itinerary_versions
                (trip_id, version, scope, program_json, approved, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (trip_id, version, scope, program_json, int(approved), now),
        )
        conn.execute(
            "UPDATE trips SET status = ?, updated_at = ? WHERE id = ?",
            ("building" if not approved else "approved", now, trip_id),
        )
        conn.commit()
        return int(cursor.lastrowid)


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
    """Пишет строку в tool_runs для eval и отладки."""
    now = _utc_now()
    args_json = json.dumps(args or {}, ensure_ascii=False)
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tool_runs (
                trip_id, itinerary_version_id, tool_name, args_json,
                provider, live_data, results_count, raw_results_count,
                error, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trip_id,
                itinerary_version_id,
                tool_name,
                args_json,
                provider,
                int(live_data),
                results_count,
                raw_results_count,
                error,
                now,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


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
    """Пишет агрегированные метрики одного прогона графа."""
    now = _utc_now()
    timings_json = (
        json.dumps(node_timings, ensure_ascii=False, separators=(",", ":"))
        if node_timings
        else None
    )
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO agent_runs (
                trip_id, run_id, rebuild_scope, duration_ms,
                prompt_tokens, completion_tokens, total_tokens, total_cost_usd,
                node_timings_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trip_id,
                run_id,
                rebuild_scope,
                int(duration_ms),
                prompt_tokens,
                completion_tokens,
                total_tokens,
                total_cost_usd,
                timings_json,
                now,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def list_agent_runs(trip_id: int | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Последние прогоны агента (по поездке или по всем поездкам)."""
    where = ""
    params: tuple[Any, ...] = (limit,)
    if trip_id is not None:
        where = "WHERE trip_id = ?"
        params = (trip_id, limit)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT trip_id, run_id, rebuild_scope, duration_ms,
                   prompt_tokens, completion_tokens, total_tokens, total_cost_usd,
                   node_timings_json, created_at
            FROM agent_runs
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        raw = item.pop("node_timings_json", None)
        if raw:
            try:
                item["node_timings"] = json.loads(raw)
            except json.JSONDecodeError:
                item["node_timings"] = None
        else:
            item["node_timings"] = None
        out.append(item)
    return out


def list_tool_runs(trip_id: int, limit: int = 50) -> list[dict[str, Any]]:
    """Последние вызовы tools для поездки."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT tool_name, provider, live_data, results_count,
                   raw_results_count, error, created_at
            FROM tool_runs
            WHERE trip_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (trip_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_latest_itinerary_approved(trip_id: int) -> None:
    """Помечает последнюю версию программы как утверждённую."""
    now = _utc_now()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id FROM itinerary_versions
            WHERE trip_id = ?
            ORDER BY version DESC
            LIMIT 1
            """,
            (trip_id,),
        ).fetchone()
        if row is None:
            return
        conn.execute(
            "UPDATE itinerary_versions SET approved = 1 WHERE id = ?",
            (int(row["id"]),),
        )
        conn.execute(
            "UPDATE trips SET status = ?, updated_at = ? WHERE id = ?",
            ("approved", now, trip_id),
        )
        conn.commit()


def list_trip_itinerary_programs(
    trip_id: int,
    *,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Программы поездки от новых к старым (для восстановления пула POI)."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT program_json
            FROM itinerary_versions
            WHERE trip_id = ?
            ORDER BY version DESC
            LIMIT ?
            """,
            (trip_id, limit),
        ).fetchall()
    programs: list[dict[str, Any]] = []
    for row in rows:
        try:
            data = json.loads(row["program_json"])
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            programs.append(data)
    return programs


def get_latest_itinerary(trip_id: int) -> dict[str, Any] | None:
    """Последняя версия программы: version, scope, program (dict), approved."""
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, version, scope, program_json, approved, created_at
            FROM itinerary_versions
            WHERE trip_id = ?
            ORDER BY version DESC
            LIMIT 1
            """,
            (trip_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "version": int(row["version"]),
        "scope": row["scope"],
        "program": json.loads(row["program_json"]),
        "approved": bool(row["approved"]),
        "created_at": row["created_at"],
    }


def get_itinerary_version(trip_id: int, version_id: int) -> dict[str, Any] | None:
    """Версия программы по id строки itinerary_versions."""
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, trip_id, version, scope, program_json, approved, created_at
            FROM itinerary_versions
            WHERE id = ? AND trip_id = ?
            """,
            (version_id, trip_id),
        ).fetchone()
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "trip_id": int(row["trip_id"]),
        "version": int(row["version"]),
        "scope": row["scope"],
        "program": json.loads(row["program_json"]),
        "approved": bool(row["approved"]),
        "created_at": row["created_at"],
    }


def list_item_feedback(trip_id: int) -> dict[str, int]:
    """Оценки пунктов поездки: {item_key: vote}. vote — 1 или -1."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT item_key, vote
            FROM program_item_feedback
            WHERE trip_id = ?
            ORDER BY updated_at ASC, id ASC
            """,
            (trip_id,),
        ).fetchall()
    return {row["item_key"]: int(row["vote"]) for row in rows}


def list_item_feedback_by_section(trip_id: int, section: str) -> dict[str, int]:
    """Оценки одной секции: {item_key: vote}."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT item_key, vote
            FROM program_item_feedback
            WHERE trip_id = ? AND section = ?
            ORDER BY updated_at ASC, id ASC
            """,
            (trip_id, section),
        ).fetchall()
    return {row["item_key"]: int(row["vote"]) for row in rows}


def list_item_feedback_by_index(trip_id: int) -> dict[tuple[str, int], int]:
    """Оценки по (section, item_index) — запасной способ после смены парсера."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT section, item_index, vote
            FROM program_item_feedback
            WHERE trip_id = ?
            ORDER BY updated_at ASC, id ASC
            """,
            (trip_id,),
        ).fetchall()
    return {(row["section"], int(row["item_index"])): int(row["vote"]) for row in rows}


def upsert_item_feedback(
    trip_id: int,
    itinerary_version_id: int | None,
    section: str,
    item_index: int,
    item_key: str,
    vote: int,
) -> None:
    """Сохраняет или обновляет оценку пункта (1 — нравится, -1 — не нравится)."""
    now = _utc_now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO program_item_feedback (
                trip_id, itinerary_version_id, section, item_index, item_key, vote, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trip_id, section, item_key)
            DO UPDATE SET
                vote = excluded.vote,
                item_index = excluded.item_index,
                itinerary_version_id = excluded.itinerary_version_id,
                updated_at = excluded.updated_at
            """,
            (trip_id, itinerary_version_id, section, item_index, item_key, vote, now),
        )
        conn.commit()


def delete_item_feedback(trip_id: int, section: str, item_key: str) -> None:
    """Удаляет оценку пункта (снятие голоса)."""
    with connect() as conn:
        conn.execute(
            """
            DELETE FROM program_item_feedback
            WHERE trip_id = ? AND section = ? AND item_key = ?
            """,
            (trip_id, section, item_key),
        )
        conn.commit()


def delete_feedback_at_index(
    trip_id: int,
    section: str,
    item_index: int,
    *,
    except_item_key: str | None = None,
) -> int:
    """Снимает «осиротевшие» оценки на том же item_index (после пересборки)."""
    with connect() as conn:
        if except_item_key:
            cursor = conn.execute(
                """
                DELETE FROM program_item_feedback
                WHERE trip_id = ? AND section = ? AND item_index = ?
                  AND item_key != ?
                """,
                (trip_id, section, item_index, except_item_key),
            )
        else:
            cursor = conn.execute(
                """
                DELETE FROM program_item_feedback
                WHERE trip_id = ? AND section = ? AND item_index = ?
                """,
                (trip_id, section, item_index),
            )
        conn.commit()
        return int(cursor.rowcount)


def save_section_artifact(
    trip_id: int,
    section: str,
    payload: dict[str, Any],
    *,
    digest: str | None = None,
) -> None:
    """Сохраняет JSON-артефакт раздела (например, кэш route_materials)."""
    now = _utc_now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO section_artifacts (trip_id, section, digest, payload_json, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(trip_id, section) DO UPDATE SET
                digest = excluded.digest,
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at
            """,
            (
                trip_id,
                section,
                digest,
                json.dumps(payload, ensure_ascii=False),
                now,
            ),
        )
        conn.commit()


def get_section_artifact(trip_id: int, section: str) -> dict[str, Any] | None:
    """Артефакт раздела: payload (dict) и digest."""
    with connect() as conn:
        row = conn.execute(
            """
            SELECT digest, payload_json
            FROM section_artifacts
            WHERE trip_id = ? AND section = ?
            """,
            (trip_id, section),
        ).fetchone()
    if row is None:
        return None
    try:
        payload = json.loads(row["payload_json"] or "{}")
    except json.JSONDecodeError:
        payload = {}
    return {
        "digest": row["digest"],
        "payload": payload if isinstance(payload, dict) else {},
    }
