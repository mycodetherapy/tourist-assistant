"""Тесты регистрации и JWT."""

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


class TestAuth(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_PATH"] = os.path.join(self._tmpdir.name, "test.db")
        init_db()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_register_login_me(self) -> None:
        reg = self.client.post(
            "/api/auth/register",
            json={"email": "user@example.com", "password": "secretpass"},
        )
        self.assertEqual(reg.status_code, 201)
        token = reg.json()["access_token"]

        bad = self.client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "wrong"},
        )
        self.assertEqual(bad.status_code, 401)

        login = self.client.post(
            "/api/auth/login",
            json={"email": "user@example.com", "password": "secretpass"},
        )
        self.assertEqual(login.status_code, 200)
        token = login.json()["access_token"]

        me = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["email"], "user@example.com")

    def test_trips_require_auth(self) -> None:
        resp = self.client.get("/api/trips")
        self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()
