"""PostgreSQL schema via Alembic (optional; skipped without DATABASE_URL)."""

from __future__ import annotations

import os
import unittest

from sqlalchemy import inspect, text

from db.constants import BOOTSTRAP_USER_EMAIL, BOOTSTRAP_USER_ID
from db.session import clear_engine_cache, get_engine, is_postgres_enabled


def _pg_available() -> bool:
    return bool(os.getenv("DATABASE_URL", "").strip() or os.getenv("TEST_DATABASE_URL", "").strip())


@unittest.skipUnless(_pg_available(), "DATABASE_URL or TEST_DATABASE_URL not set")
class PostgresSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
        assert url
        os.environ["DATABASE_URL"] = url
        clear_engine_cache()

    def test_core_tables_exist(self) -> None:
        engine = get_engine()
        names = set(inspect(engine).get_table_names())
        expected = {
            "users",
            "user_settings",
            "trips",
            "trip_preferences",
            "user_profile",
            "itinerary_versions",
            "tool_runs",
            "agent_runs",
            "program_item_feedback",
            "section_artifacts",
            "graph_runs",
            "city_packs",
            "audit_events",
            "usage_events",
            "alembic_version",
        }
        missing = expected - names
        self.assertFalse(missing, f"missing tables: {missing}")
        self.assertNotIn("affiliate_clicks", names)

    def test_bootstrap_user_seeded(self) -> None:
        engine = get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT id, email FROM users WHERE id = :id"),
                {"id": BOOTSTRAP_USER_ID},
            ).one()
        self.assertEqual(int(row[0]), BOOTSTRAP_USER_ID)
        self.assertEqual(str(row[1]), BOOTSTRAP_USER_EMAIL)

    def test_postgres_flag(self) -> None:
        self.assertTrue(is_postgres_enabled())


if __name__ == "__main__":
    unittest.main()
