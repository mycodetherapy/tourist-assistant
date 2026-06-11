"""BYOK: ключ в настройках и 428 без ключа."""

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


class TestLlmByok(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_PATH"] = os.path.join(self._tmpdir.name, "test.db")
        init_db()
        self.client = TestClient(app)
        reg = self.client.post(
            "/api/auth/register",
            json={"email": "byok@example.com", "password": "password123"},
        )
        self.token = reg.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_start_run_without_key_returns_428(self) -> None:
        create = self.client.post(
            "/api/trips",
            headers=self.headers,
            json={
                "city": "Сочи",
                "dates": "август 2026",
                "origin_city": "Москва",
                "preferences": _PREFS,
                "start_run": True,
            },
        )
        self.assertEqual(create.status_code, 428)
        detail = create.json()["detail"]
        self.assertEqual(detail["code"], "llm_key_required")
        trips = self.client.get("/api/trips", headers=self.headers)
        self.assertEqual(trips.json(), [])

    def test_settings_save_and_preview(self) -> None:
        put = self.client.put(
            "/api/profile/settings",
            headers=self.headers,
            json={"llm_api_key": "sk-or-test-key-abcdefghij"},
        )
        self.assertEqual(put.status_code, 200)
        body = put.json()
        self.assertTrue(body["llm_key_configured"])
        self.assertIn("...", body["llm_key_preview"])
        self.assertNotIn("sk-or-test-key-abcdefghij", body["llm_key_preview"])

        get = self.client.get("/api/profile/settings", headers=self.headers)
        self.assertTrue(get.json()["llm_key_configured"])


if __name__ == "__main__":
    unittest.main()
