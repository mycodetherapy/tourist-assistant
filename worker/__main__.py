"""RQ worker entrypoint: python -m worker"""

from __future__ import annotations

import os
import platform
import sys

from rq import SimpleWorker, Worker

from db.redis_client import get_redis


def _worker_class():
    """macOS: fork в RQ ломает LangGraph/SQLAlchemy (SIGABRT в work-horse)."""
    if platform.system() == "Darwin":
        return SimpleWorker
    if os.getenv("RQ_SIMPLE_WORKER", "").strip().lower() in ("1", "true", "yes"):
        return SimpleWorker
    return Worker


def main() -> None:
    conn = get_redis()
    queues = os.getenv("RQ_QUEUES", "build_routes,city_fact,default").split(",")
    queues = [q.strip() for q in queues if q.strip()]
    worker = _worker_class()(queues, connection=conn)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    sys.exit(main() or 0)
