"""Tests for Redis run quotas."""

from __future__ import annotations

import os
import unittest
from unittest import skipUnless

from db.redis_client import clear_redis_cache, get_redis
from services.run_quotas import (
    RunQuotaError,
    check_and_consume_run_quota,
    clear_quota_cache,
)


def _redis_configured() -> bool:
    return bool(os.getenv("REDIS_URL", "").strip())


@skipUnless(_redis_configured(), "REDIS_URL required")
class RunQuotaTests(unittest.TestCase):
    user_id = 88001

    def setUp(self) -> None:
        self._prev_quotas = os.environ.get("RUN_QUOTAS_ENABLED")
        os.environ["RUN_QUOTAS_ENABLED"] = "true"
        clear_quota_cache()
        pattern = f"run_quota:{self.user_id}:*"
        for key in get_redis().scan_iter(match=pattern):
            get_redis().delete(key)

    def tearDown(self) -> None:
        if self._prev_quotas is None:
            os.environ.pop("RUN_QUOTAS_ENABLED", None)
        else:
            os.environ["RUN_QUOTAS_ENABLED"] = self._prev_quotas
        clear_redis_cache()

    def test_allows_up_to_limit(self) -> None:
        limit = int(os.getenv("RUN_QUOTA_FULL_PER_HOUR", "10"))
        for _ in range(limit):
            check_and_consume_run_quota(user_id=self.user_id, scope="full")
        with self.assertRaises(RunQuotaError):
            check_and_consume_run_quota(user_id=self.user_id, scope="full")

    def test_partial_bucket_separate(self) -> None:
        for _ in range(10):
            check_and_consume_run_quota(user_id=self.user_id, scope="routes")
        check_and_consume_run_quota(user_id=self.user_id, scope="full")

    def test_disabled_via_env(self) -> None:
        os.environ["RUN_QUOTAS_ENABLED"] = "false"
        clear_quota_cache()
        for _ in range(10):
            check_and_consume_run_quota(user_id=self.user_id, scope="full")
        os.environ.pop("RUN_QUOTAS_ENABLED", None)
        clear_quota_cache()


if __name__ == "__main__":
    unittest.main()
