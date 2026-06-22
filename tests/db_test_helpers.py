"""Изоляция PostgreSQL в unit-тестах."""

from __future__ import annotations

import os
import unittest

from sqlalchemy import text

from db.session import clear_engine_cache, get_engine, is_postgres_enabled


def pg_available() -> bool:
    return bool(
        os.getenv("DATABASE_URL", "").strip()
        or os.getenv("TEST_DATABASE_URL", "").strip()
    )


def skip_unless_pg(test_item):
    return unittest.skipUnless(pg_available(), "DATABASE_URL or TEST_DATABASE_URL not set")(
        test_item
    )


def prepare_pg_env() -> None:
    url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    assert url
    os.environ["DATABASE_URL"] = url
    clear_engine_cache()
    assert is_postgres_enabled()


def truncate_pg_tables() -> None:
    prepare_pg_env()
    engine = get_engine()
    tables = (
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
    with engine.begin() as conn:
        for table in tables:
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
