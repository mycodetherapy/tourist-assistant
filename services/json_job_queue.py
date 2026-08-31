"""JSON job queue in Redis (enqueue from Node.js or Python API)."""

from __future__ import annotations

import json
from typing import Any

QUEUE_BUILD_ROUTES = "tourist:queue:build_routes"
QUEUE_CITY_FACT = "tourist:queue:city_fact"
QUEUE_POI_FACT = "tourist:queue:poi_fact"
QUEUE_PREPARE_CITY_PACK = "tourist:queue:prepare_city_pack"
QUEUE_PREPARE_OSRM = "tourist:queue:prepare_osrm"


def push_job(
    queue_name: str,
    *,
    task: str,
    graph_run_id: str,
    payload: dict[str, Any],
) -> None:
    from db.redis_client import get_redis

    body = json.dumps(
        {
            "task": task,
            "graph_run_id": graph_run_id,
            "payload": payload,
        },
        ensure_ascii=False,
    )
    get_redis().rpush(queue_name, body.encode("utf-8"))


def pop_job(timeout_sec: int = 5) -> tuple[str, dict[str, Any]] | None:
    """BLPOP from build_routes or city_fact queues."""
    from redis.exceptions import TimeoutError as RedisTimeoutError

    from db.redis_client import get_redis

    try:
        result = get_redis().blpop(
            [
                QUEUE_BUILD_ROUTES,
                QUEUE_CITY_FACT,
                QUEUE_POI_FACT,
                QUEUE_PREPARE_CITY_PACK,
                QUEUE_PREPARE_OSRM,
            ],
            timeout=timeout_sec,
        )
    except RedisTimeoutError:
        # Пустая очередь: redis-py может бросить вместо None при socket_timeout
        return None
    if result is None:
        return None
    queue_name, raw = result
    qname = (
        queue_name.decode("utf-8")
        if isinstance(queue_name, bytes)
        else str(queue_name)
    )
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    job = json.loads(raw)
    return qname, job
