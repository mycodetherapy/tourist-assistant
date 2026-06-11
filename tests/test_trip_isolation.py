"""Изоляция поездок между пользователями."""

from __future__ import annotations

import os
import tempfile
import unittest

from cryptography.fernet import Fernet

os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-unit-tests-only")
os.environ.setdefault("SETTINGS_ENCRYPTION_KEY", Fernet.generate_key().decode())

from fastapi.testclient import TestClient

from api.main import app
from db.connection import init_db

_PREFS = {
    "travel_party": "couple",
    "pace": "moderate",
    "budget": "medium",
    "transport_preference": "mixed",
    "interests": ["музеи"],
}


class TestTripIsolation(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_PATH"] = os.path.join(self._tmpdir.name, "test.db")
        init_db()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _register(self, email: str) -> str:
        resp = self.client.post(
            "/api/auth/register",
            json={"email": email, "password": "password123"},
        )
        self.assertEqual(resp.status_code, 201)
        return resp.json()["access_token"]

    def test_user_cannot_see_other_trips(self) -> None:
        token_a = self._register("a@example.com")
        token_b = self._register("b@example.com")

        create = self.client.post(
            "/api/trips",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "city": "Москва",
                "dates": "1-3 июля 2026",
                "origin_city": "Казань",
                "preferences": _PREFS,
                "start_run": False,
            },
        )
        self.assertEqual(create.status_code, 201)
        trip_id = create.json()["trip_id"]

        list_b = self.client.get(
            "/api/trips",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        self.assertEqual(list_b.status_code, 200)
        self.assertEqual(list_b.json(), [])

        get_b = self.client.get(
            f"/api/trips/{trip_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        self.assertEqual(get_b.status_code, 404)


if __name__ == "__main__":
    unittest.main()
