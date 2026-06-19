"""RQ job enqueue."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from rq import Queue

from db.redis_client import get_redis

_ON_FAILURE = "worker.callbacks.on_graph_job_failure"


def get_queue(name: str = "default") -> Queue:
    return Queue(name, connection=get_redis())


def enqueue_build_routes(*, graph_run_id: UUID, payload: dict[str, Any]) -> str:
    job = get_queue("build_routes").enqueue(
        "worker.tasks.build_routes_task",
        str(graph_run_id),
        payload,
        job_timeout=1800,
        on_failure=_ON_FAILURE,
    )
    return job.id


def enqueue_city_fact(*, graph_run_id: UUID, payload: dict[str, Any]) -> str:
    job = get_queue("city_fact").enqueue(
        "worker.tasks.city_fact_task",
        str(graph_run_id),
        payload,
        job_timeout=600,
        on_failure=_ON_FAILURE,
    )
    return job.id
