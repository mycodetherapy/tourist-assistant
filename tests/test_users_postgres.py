"""PostgreSQL users/auth storage tests."""

from __future__ import annotations

import unittest

from db.backends import get_users_backend
from db.users import (
    User,
    clear_user_llm_key,
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_user_settings,
    upsert_user_settings,
)
from tests.db_test_helpers import prepare_pg_env, skip_unless_test_pg, truncate_users_tables


@skip_unless_test_pg
class PostgresUsersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        prepare_pg_env()
        cls._backend = get_users_backend().__name__

    def setUp(self) -> None:
        truncate_users_tables()

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
