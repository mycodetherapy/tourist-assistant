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


def _migrate_saas_auth(conn: sqlite3.Connection) -> None:
    """Миграция: users, user_settings, user_id в trips, per-user user_profile."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT,
            google_sub TEXT UNIQUE,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            llm_api_key_enc TEXT,
            llm_base_url TEXT,
            llm_model TEXT,
            updated_at TEXT NOT NULL
        );
        """
    )
    from db.constants import (
        BOOTSTRAP_USER_EMAIL,
        BOOTSTRAP_USER_ID,
        LEGACY_BOOTSTRAP_EMAIL,
    )
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    bootstrap = conn.execute("SELECT id FROM users WHERE id = ?", (BOOTSTRAP_USER_ID,)).fetchone()
    if bootstrap is None:
        conn.execute(
            """
            INSERT INTO users (id, email, password_hash, google_sub, created_at, updated_at)
            VALUES (?, ?, NULL, NULL, ?, ?)
            """,
            (BOOTSTRAP_USER_ID, BOOTSTRAP_USER_EMAIL, now, now),
        )
    else:
        conn.execute(
            """
            UPDATE users SET email = ?, updated_at = ?
            WHERE id = ? AND email = ?
            """,
            (BOOTSTRAP_USER_EMAIL, now, BOOTSTRAP_USER_ID, LEGACY_BOOTSTRAP_EMAIL),
        )

    trip_cols = {r[1] for r in conn.execute("PRAGMA table_info(trips)").fetchall()}
    if "user_id" not in trip_cols:
        conn.execute(
            "ALTER TABLE trips ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE"
        )
        conn.execute(
            "UPDATE trips SET user_id = ? WHERE user_id IS NULL",
            (BOOTSTRAP_USER_ID,),
        )

    profile_row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='user_profile'"
    ).fetchone()
    if profile_row is not None:
        profile_cols = {
            r[1] for r in conn.execute("PRAGMA table_info(user_profile)").fetchall()
        }
        if "id" in profile_cols and "user_id" not in profile_cols:
            conn.execute("ALTER TABLE user_profile RENAME TO user_profile_legacy")
            conn.executescript(
                """
                CREATE TABLE user_profile (
                    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    preferences_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            legacy = conn.execute(
                "SELECT preferences_json, updated_at FROM user_profile_legacy WHERE id = 1"
            ).fetchone()
            if legacy is not None:
                conn.execute(
                    """
                    INSERT INTO user_profile (user_id, preferences_json, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    (BOOTSTRAP_USER_ID, legacy[0], legacy[1]),
                )
            conn.execute("DROP TABLE user_profile_legacy")

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_trips_user ON trips(user_id)"
    )


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
        _migrate_saas_auth(conn)
        _migrate_program_item_feedback(conn)
        _migrate_agent_runs_timings(conn)
        _migrate_affiliate_clicks(conn)
        conn.commit()
