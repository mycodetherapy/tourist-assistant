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


def init_db() -> None:
    """Создаёт таблицы по schema.sql, если их ещё нет."""
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    with connect() as conn:
        conn.executescript(schema_sql)
        _migrate_program_item_feedback(conn)
        conn.commit()
