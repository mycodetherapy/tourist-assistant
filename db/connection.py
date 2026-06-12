"""Подключение к SQLite: путь из DATABASE_PATH, инициализация схемы."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_database_path() -> str:
    """Возвращает путь к файлу БД (по умолчанию data/trips.db)."""
    raw = os.getenv("DATABASE_PATH", "data/trips.db").strip()
    return raw or "data/trips.db"


def connect() -> sqlite3.Connection:
    """Открывает соединение с включёнными foreign keys."""
    path = get_database_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate_program_item_feedback(conn: sqlite3.Connection) -> None:
    """Добавляет item_key в program_item_feedback без удаления старых строк."""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='program_item_feedback'"
    ).fetchone()
    if row is None:
        return
    columns = {
        r[1] for r in conn.execute("PRAGMA table_info(program_item_feedback)").fetchall()
    }
    if "item_key" in columns:
        return
    conn.execute(
        "ALTER TABLE program_item_feedback RENAME TO program_item_feedback_legacy"
    )
    conn.executescript(
        """
        CREATE TABLE program_item_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
            itinerary_version_id INTEGER REFERENCES itinerary_versions(id) ON DELETE SET NULL,
            section TEXT NOT NULL,
            item_index INTEGER NOT NULL,
            item_key TEXT NOT NULL,
            vote INTEGER NOT NULL CHECK (vote IN (1, -1)),
            updated_at TEXT NOT NULL,
            UNIQUE(trip_id, section, item_key)
        );
        CREATE INDEX IF NOT EXISTS idx_program_feedback_trip ON program_item_feedback(trip_id);
        """
    )


def _migrate_agent_runs_timings(conn: sqlite3.Connection) -> None:
    """Добавляет node_timings_json в agent_runs для per-node метрик."""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_runs'"
    ).fetchone()
    if row is None:
        return
    columns = {r[1] for r in conn.execute("PRAGMA table_info(agent_runs)").fetchall()}
    if "node_timings_json" in columns:
        return
    conn.execute("ALTER TABLE agent_runs ADD COLUMN node_timings_json TEXT")


def _migrate_user_profile(conn: sqlite3.Connection) -> None:
    """Legacy SaaS: user_profile(user_id) → локальный singleton id=1."""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='user_profile'"
    ).fetchone()
    if row is None:
        return
    columns = {r[1] for r in conn.execute("PRAGMA table_info(user_profile)").fetchall()}
    if "id" in columns:
        return
    if "user_id" not in columns:
        return

    legacy_row = conn.execute(
        """
        SELECT preferences_json, updated_at
        FROM user_profile
        ORDER BY CASE WHEN user_id = 1 THEN 0 ELSE 1 END, updated_at DESC
        LIMIT 1
        """
    ).fetchone()

    conn.execute("ALTER TABLE user_profile RENAME TO user_profile_legacy")
    conn.executescript(
        """
        CREATE TABLE user_profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            preferences_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    if legacy_row is not None:
        conn.execute(
            """
            INSERT INTO user_profile (id, preferences_json, updated_at)
            VALUES (1, ?, ?)
            """,
            (legacy_row[0], legacy_row[1]),
        )
    conn.execute("DROP TABLE user_profile_legacy")


def _migrate_affiliate_clicks(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='affiliate_clicks'"
    ).fetchone()
    if row is not None:
        return
    conn.executescript(
        """
        CREATE TABLE affiliate_clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
            channel TEXT NOT NULL DEFAULT 'tickets',
            provider TEXT,
            target_url TEXT NOT NULL,
            sub_id TEXT,
            clicked_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_affiliate_clicks_trip ON affiliate_clicks(trip_id);
        CREATE INDEX IF NOT EXISTS idx_affiliate_clicks_clicked ON affiliate_clicks(clicked_at DESC);
        """
    )


def init_db() -> None:
    """Создаёт таблицы по schema.sql, если их ещё нет."""
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    with connect() as conn:
        conn.executescript(schema_sql)
        _migrate_program_item_feedback(conn)
        _migrate_agent_runs_timings(conn)
        _migrate_user_profile(conn)
        _migrate_affiliate_clicks(conn)
        conn.commit()
