"""Guard: tests must not TRUNCATE dev database."""

from __future__ import annotations

import unittest

from tests.db_test_helpers import assert_safe_test_database_url, resolve_test_database_url


class TestDatabaseSafety(unittest.TestCase):
    def test_refuses_dev_database_without_override(self) -> None:
        with self.assertRaises(RuntimeError):
            assert_safe_test_database_url(
                "postgresql+psycopg://tourist:tourist@localhost:5433/tourist"
            )

    def test_allows_test_database(self) -> None:
        assert_safe_test_database_url(
            "postgresql+psycopg://tourist:tourist@localhost:5433/tourist_test"
        )

    def test_resolve_requires_test_suffix(self) -> None:
        import os

        prev = os.environ.get("TEST_DATABASE_URL")
        os.environ["TEST_DATABASE_URL"] = (
            "postgresql+psycopg://tourist:tourist@localhost:5433/tourist_test"
        )
        try:
            url = resolve_test_database_url()
            self.assertTrue(url.endswith("/tourist_test"))
        finally:
            if prev is None:
                os.environ.pop("TEST_DATABASE_URL", None)
            else:
                os.environ["TEST_DATABASE_URL"] = prev


if __name__ == "__main__":
    unittest.main()
