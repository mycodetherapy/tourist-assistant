"""RQ worker entrypoint: python -m worker"""

from __future__ import annotations

import os
import sys

from rq import Worker

from db.redis_client import get_redis


def main() -> None:
    conn = get_redis()
    queues = os.getenv("RQ_QUEUES", "build_routes,city_fact,default").split(",")
    queues = [q.strip() for q in queues if q.strip()]
    worker = Worker(queues, connection=conn)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    sys.exit(main() or 0)
