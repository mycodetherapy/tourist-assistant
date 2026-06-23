"""Tests for audit/usage events (Postgres)."""

from __future__ import annotations

import unittest

from sqlalchemy import select, text

from db.postgres import audit as pg_audit
from db.postgres import usage as pg_usage
from db.models.schema import AuditEvent, UsageEvent
from db.session import pg_session
from tests.db_test_helpers import prepare_pg_env, skip_unless_test_pg


def _truncate() -> None:
    with pg_session() as session:
        session.execute(text("TRUNCATE usage_events, audit_events RESTART IDENTITY CASCADE"))


def _seed_user(user_id: int = 7701) -> None:
    with pg_session() as session:
        session.execute(
            text(
                """
                INSERT INTO users (id, email, created_at, updated_at)
                VALUES (:uid, :email, NOW(), NOW())
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"uid": user_id, "email": f"saas-{user_id}@test.local"},
        )


@skip_unless_test_pg
class SaasEventsTests(unittest.TestCase):
    user_id = 7701

    @classmethod
    def setUpClass(cls) -> None:
        prepare_pg_env()
        _truncate()
        _seed_user(cls.user_id)

    def setUp(self) -> None:
        _truncate()

    def test_record_audit(self) -> None:
        row_id = pg_audit.record_audit_event(
            action="trip.create",
            entity_type="trip",
            entity_id="42",
            user_id=self.user_id,
            metadata={"city": "Казань"},
        )
        self.assertGreater(row_id, 0)
        with pg_session() as session:
            row = session.get(AuditEvent, row_id)
            assert row is not None
            self.assertEqual(row.action, "trip.create")

    def test_record_usage(self) -> None:
        row_id = pg_usage.record_usage_event(
            user_id=self.user_id,
            source="graph:full",
            trip_id=None,
            prompt_tokens=100,
            total_tokens=150,
        )
        with pg_session() as session:
            count = session.execute(
                select(UsageEvent.id).where(UsageEvent.id == row_id)
            ).first()
        self.assertIsNotNone(count)

    def test_saas_events_facade_noop_without_pg(self) -> None:
        from services import saas_events

        saas_events.audit(
            action="test",
            entity_type="trip",
            entity_id="1",
            user_id=1,
        )


if __name__ == "__main__":
    unittest.main()
