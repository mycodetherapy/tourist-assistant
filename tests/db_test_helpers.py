"""Изоляция PostgreSQL в unit-тестах."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import text

from db.session import clear_engine_cache, get_engine, is_postgres_enabled

_DOTENV_LOADED = False


def _ensure_dotenv_loaded() -> None:
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    try:
        from dotenv import load_dotenv

        root = Path(__file__).resolve().parents[1]
        load_dotenv(root / ".env")
    except ImportError:
        pass
    _DOTENV_LOADED = True


def _database_name(url: str) -> str:
    parsed = urlparse(url.replace("+psycopg", ""))
    name = (parsed.path or "").lstrip("/").split("?")[0].strip()
    if not name:
        raise ValueError(f"Cannot parse database name from URL: {url!r}")
    return name


def assert_safe_test_database_url(url: str) -> None:
    """Запрет TRUNCATE на dev/prod БД без явного override."""
    if os.getenv("ALLOW_TEST_TRUNCATE", "").strip() == "1":
        return
    db_name = _database_name(url)
    if not db_name.endswith("_test"):
        raise RuntimeError(
            f"Refusing to TRUNCATE database {db_name!r}. "
            "Set TEST_DATABASE_URL to a database ending with '_test' "
            "(e.g. postgresql+psycopg://tourist:tourist@localhost:5433/tourist_test), "
            "or set ALLOW_TEST_TRUNCATE=1 to override."
        )


def resolve_test_database_url() -> str:
    _ensure_dotenv_loaded()
    url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "TEST_DATABASE_URL is required for PostgreSQL tests that mutate data. "
            "Create the database (see scripts/ensure_test_database.py) and add "
            "TEST_DATABASE_URL=.../tourist_test to .env."
        )
    assert_safe_test_database_url(url)
    return url


def test_pg_available() -> bool:
    _ensure_dotenv_loaded()
    url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not url:
        return False
    try:
        assert_safe_test_database_url(url)
    except RuntimeError:
        return False
    return True


def pg_available() -> bool:
    """Любой Postgres URL (dev или test) — только для read-only проверок."""
    _ensure_dotenv_loaded()
    return bool(
        os.getenv("TEST_DATABASE_URL", "").strip()
        or os.getenv("DATABASE_URL", "").strip()
    )


def skip_unless_test_pg(test_item):
    return unittest.skipUnless(
        test_pg_available(), "TEST_DATABASE_URL (…/_test) required"
    )(test_item)


def skip_unless_pg(test_item):
    return skip_unless_test_pg(test_item)


def prepare_pg_env() -> None:
    url = resolve_test_database_url()
    os.environ["DATABASE_URL"] = url
    clear_engine_cache()
    assert is_postgres_enabled()


_TRUNCATE_TABLES = (
    "usage_events",
    "graph_runs",
    "program_item_feedback",
    "tool_runs",
    "agent_runs",
    "itinerary_versions",
    "section_artifacts",
    "trip_preferences",
    "trips",
    "user_profile",
    "user_settings",
    "audit_events",
)


def truncate_pg_tables() -> None:
    prepare_pg_env()
    engine = get_engine()
    with engine.begin() as conn:
        for table in _TRUNCATE_TABLES:
            conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
        conn.execute(
            text(
                """
                INSERT INTO users (id, email, password_hash, google_sub, created_at, updated_at)
                VALUES (1, 'system@local', NULL, NULL, NOW(), NOW())
                ON CONFLICT (email) DO NOTHING
                """
            )
        )
        conn.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('users', 'id'), "
                "GREATEST(1, (SELECT MAX(id) FROM users)))"
            )
        )


def truncate_users_tables() -> None:
    prepare_pg_env()
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE user_settings, users RESTART IDENTITY CASCADE"))
        conn.execute(
            text(
                """
                INSERT INTO users (id, email, password_hash, google_sub, created_at, updated_at)
                VALUES (1, 'system@local', NULL, NULL, NOW(), NOW())
                ON CONFLICT (email) DO NOTHING
                """
            )
        )
        conn.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('users', 'id'), "
                "GREATEST(1, (SELECT MAX(id) FROM users)))"
            )
        )
