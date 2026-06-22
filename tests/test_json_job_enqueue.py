"""Tests for JSON job enqueue (Redis)."""

from __future__ import annotations

import json
import os
import unittest
from unittest import skipUnless
from uuid import uuid4

from db.redis_client import clear_redis_cache, get_redis
from services.json_job_queue import QUEUE_BUILD_ROUTES, pop_job, push_job


def _redis_configured() -> bool:
    return bool(os.getenv("REDIS_URL", "").strip())


@skipUnless(_redis_configured(), "REDIS_URL required")
class JsonJobEnqueueTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_redis_cache()
        client = get_redis()
        for key in client.scan_iter("tourist:queue:*"):
            client.delete(key)

    def tearDown(self) -> None:
        clear_redis_cache()

    def test_push_and_pop_job(self) -> None:
        run_id = str(uuid4())
        push_job(
            QUEUE_BUILD_ROUTES,
            task="build_routes",
            graph_run_id=run_id,
            payload={"trip_id": 1, "user_id": 2, "scope": "full"},
        )
        client = get_redis()
        self.assertEqual(client.llen(QUEUE_BUILD_ROUTES), 1)
        item = pop_job(timeout_sec=1)
        self.assertIsNotNone(item)
        queue_name, job = item  # type: ignore[misc]
        self.assertEqual(queue_name, QUEUE_BUILD_ROUTES)
        self.assertEqual(job["task"], "build_routes")
        self.assertEqual(job["graph_run_id"], run_id)
        self.assertEqual(job["payload"]["trip_id"], 1)


if __name__ == "__main__":
    unittest.main()
