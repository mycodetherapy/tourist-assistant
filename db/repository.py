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


def save_itinerary_version(
    trip_id: int,
    program: dict[str, Any],
    *,
    scope: str = "full",
    approved: bool = False,
) -> int:
    """Сохраняет версию программы; возвращает id записи itinerary_versions."""
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
