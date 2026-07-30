"""Tests for RQ enqueue (Redis binary mode). Legacy; skip if rq is not installed."""

from __future__ import annotations

import importlib.util
import os
import unittest
from unittest import skipUnless

from db.redis_client import clear_redis_cache, get_redis

RQ_AVAILABLE = importlib.util.find_spec("rq") is not None


def _noop_task() -> str:
    return "ok"


def _redis_configured() -> bool:
    return bool(os.getenv("REDIS_URL", "").strip())


@skipUnless(RQ_AVAILABLE and _redis_configured(), "rq package and REDIS_URL required")
class RqEnqueueTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_redis_cache()
        client = get_redis()
        for key in client.scan_iter("rq:*"):
            client.delete(key)

    def tearDown(self) -> None:
        clear_redis_cache()

    def test_enqueue_puts_job_in_queue(self) -> None:
        from rq import Queue

        conn = get_redis()
        q = Queue("rq_test_only", connection=conn)
        job = q.enqueue("tests.test_rq_enqueue._noop_task")
        self.assertEqual(q.count, 1)
        self.assertIn(job.id, q.job_ids)


if __name__ == "__main__":
    unittest.main()
