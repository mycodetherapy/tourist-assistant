"""Tests for RQ enqueue (Redis binary mode)."""

from __future__ import annotations

import os
import unittest
from unittest import skipUnless

from rq import Queue

from db.redis_client import clear_redis_cache, get_redis


def _redis_configured() -> bool:
    return bool(os.getenv("REDIS_URL", "").strip())


@skipUnless(_redis_configured(), "REDIS_URL required")
class RqEnqueueTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_redis_cache()
        client = get_redis()
        for key in client.scan_iter("rq:*"):
            client.delete(key)

    def tearDown(self) -> None:
        clear_redis_cache()

    def test_enqueue_puts_job_in_queue(self) -> None:
        conn = get_redis()
        q = Queue("build_routes", connection=conn)
        job = q.enqueue("worker.tasks.build_routes_task", "00000000-0000-0000-0000-000000000001", {"trip_id": 1})
        self.assertEqual(q.count, 1)
        self.assertIn(job.id, q.job_ids)


if __name__ == "__main__":
    unittest.main()
