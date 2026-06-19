"""Tests for graph_runs (Postgres + Redis lock)."""

from __future__ import annotations

import os
import unittest
import uuid
from unittest import skipUnless

from sqlalchemy import text

from db.postgres import graph_runs as pg_runs
from db.redis_client import clear_redis_cache, get_redis
from db.session import is_postgres_enabled, pg_session


def _pg_configured() -> bool:
    return is_postgres_enabled() and bool(os.getenv("REDIS_URL", "").strip())


def _truncate_graph_runs() -> None:
    with pg_session() as session:
        session.execute(text("TRUNCATE graph_runs RESTART IDENTITY CASCADE"))


def _seed_trip(*, user_id: int = 1, trip_id: int = 9001) -> None:
    with pg_session() as session:
        session.execute(
            text(
                """
                INSERT INTO users (id, email, created_at, updated_at)
                VALUES (:uid, :email, NOW(), NOW())
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"uid": user_id, "email": f"gr-{user_id}@test.local"},
        )
        session.execute(
            text(
                """
                INSERT INTO trips (id, user_id, city, dates, origin_city, status, created_at, updated_at)
                VALUES (:tid, :uid, 'Казань', '3 дня', 'Москва', 'active', NOW(), NOW())
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"tid": trip_id, "uid": user_id},
        )


@skipUnless(_pg_configured(), "DATABASE_URL and REDIS_URL required")
class GraphRunsTests(unittest.TestCase):
    trip_id = 9001
    user_id = 1

    @classmethod
    def setUpClass(cls) -> None:
        clear_redis_cache()
        _truncate_graph_runs()
        _seed_trip(user_id=cls.user_id, trip_id=cls.trip_id)

    def setUp(self) -> None:
        _truncate_graph_runs()
        get_redis().delete(f"trip:{self.trip_id}:build_lock")

    def test_create_and_get(self) -> None:
        run_id = pg_runs.create_graph_run(
            user_id=self.user_id,
            trip_id=self.trip_id,
            scope="full",
            city_fact_status="pending",
        )
        row = pg_runs.get_graph_run(run_id)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["status"], "queued")
        self.assertEqual(row["scope"], "full")
        self.assertEqual(row["city_fact_status"], "pending")

    def test_update_and_active_check(self) -> None:
        run_id = pg_runs.create_graph_run(
            user_id=self.user_id,
            trip_id=self.trip_id,
            scope="routes",
        )
        self.assertTrue(pg_runs.has_active_graph_run(self.trip_id))
        pg_runs.update_graph_run(run_id, status="running")
        self.assertTrue(pg_runs.has_active_graph_run(self.trip_id))
        pg_runs.update_graph_run(run_id, status="completed")
        self.assertFalse(pg_runs.has_active_graph_run(self.trip_id))

    def test_build_lock(self) -> None:
        self.assertTrue(pg_runs.acquire_trip_build_lock(self.trip_id, ttl_sec=60))
        self.assertFalse(pg_runs.acquire_trip_build_lock(self.trip_id, ttl_sec=60))
        pg_runs.release_trip_build_lock(self.trip_id)
        self.assertTrue(pg_runs.acquire_trip_build_lock(self.trip_id, ttl_sec=60))

    def test_get_missing(self) -> None:
        self.assertIsNone(pg_runs.get_graph_run(uuid.uuid4()))


if __name__ == "__main__":
    unittest.main()
