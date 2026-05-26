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


def init_db() -> None:
    """Создаёт таблицы по schema.sql, если их ещё нет."""
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    with connect() as conn:
        conn.executescript(schema_sql)
        conn.commit()
