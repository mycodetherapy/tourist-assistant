"""PostgreSQL users/auth storage tests."""

from __future__ import annotations

import os
import unittest
from unittest import skipUnless

from sqlalchemy import text

from db.backends import get_users_backend
from db.session import clear_engine_cache, get_engine, is_postgres_enabled
from db.users import (
    User,
    clear_user_llm_key,
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_user_settings,
    upsert_user_settings,
)


def _pg_available() -> bool:
    return bool(os.getenv("DATABASE_URL", "").strip())


def _truncate_users() -> None:
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
                "SELECT setval(pg_get_serial_sequence('users', 'id'), GREATEST(1, (SELECT MAX(id) FROM users)))"
            )
        )


@skipUnless(_pg_available(), "DATABASE_URL required")
class PostgresUsersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        clear_engine_cache()
        cls._backend = get_users_backend().__name__

    def setUp(self) -> None:
        _truncate_users()

    def test_backend_is_postgres(self) -> None:
        self.assertEqual(self._backend, "db.postgres.users")

    def test_create_and_lookup(self) -> None:
        user = create_user(email="PgUser@Example.com", password_hash="hash")
        self.assertIsInstance(user, User)
        self.assertEqual(user.email, "pguser@example.com")
        by_id = get_user_by_id(user.id)
        assert by_id is not None
        self.assertEqual(by_id.email, user.email)
        by_email = get_user_by_email("PGUSER@example.com")
        assert by_email is not None
        self.assertEqual(by_email.id, user.id)

    def test_settings_upsert(self) -> None:
        user = create_user(email="settings@test.local")
        row = upsert_user_settings(
            user.id,
            llm_api_key_enc="enc",
            llm_base_url="https://openrouter.ai/api/v1",
            llm_model="openai/gpt-4.1-mini",
        )
        self.assertEqual(row.llm_api_key_enc, "enc")
        updated = upsert_user_settings(user.id, llm_model="other/model")
        self.assertEqual(updated.llm_model, "other/model")
        self.assertEqual(updated.llm_api_key_enc, "enc")
        clear_user_llm_key(user.id)
        cleared = get_user_settings(user.id)
        assert cleared is not None
        self.assertIsNone(cleared.llm_api_key_enc)


if __name__ == "__main__":
    unittest.main()
