"""Tests for free daily run quotas."""

from __future__ import annotations

import os
import unittest

from tests.db_test_helpers import prepare_pg_env, skip_unless_test_pg
from services.free_run_quotas import (
    FreeRunQuotaError,
    check_and_consume_free_run_quota,
    clear_free_quota_cache,
)


@skip_unless_test_pg
class FreeRunQuotaTests(unittest.TestCase):
    user_id = 9001

    def setUp(self) -> None:
        prepare_pg_env()
        self._prev = os.environ.get("FREE_RUN_QUOTAS_ENABLED")
        os.environ["FREE_RUN_QUOTAS_ENABLED"] = "true"
        os.environ["FREE_RUN_QUOTA_PER_DAY"] = "2"
        clear_free_quota_cache()
        pattern = f"free_run_quota:{self.user_id}:*"
        from db.redis_client import get_redis

        for key in get_redis().scan_iter(match=pattern):
            get_redis().delete(key)

    def tearDown(self) -> None:
        if self._prev is None:
            os.environ.pop("FREE_RUN_QUOTAS_ENABLED", None)
        else:
            os.environ["FREE_RUN_QUOTAS_ENABLED"] = self._prev
        os.environ.pop("FREE_RUN_QUOTA_PER_DAY", None)
        clear_free_quota_cache()

    def test_daily_limit(self) -> None:
        check_and_consume_free_run_quota(user_id=self.user_id)
        check_and_consume_free_run_quota(user_id=self.user_id)
        with self.assertRaises(FreeRunQuotaError):
            check_and_consume_free_run_quota(user_id=self.user_id)


if __name__ == "__main__":
    unittest.main()
