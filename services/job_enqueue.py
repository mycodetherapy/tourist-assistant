"""Job enqueue via JSON Redis queues (Node.js + Python API compatible)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from services.json_job_queue import QUEUE_BUILD_ROUTES, QUEUE_CITY_FACT, QUEUE_PREPARE_CITY_PACK, push_job


def enqueue_build_routes(*, graph_run_id: UUID, payload: dict[str, Any]) -> str:
    push_job(
        QUEUE_BUILD_ROUTES,
        task="build_routes",
        graph_run_id=str(graph_run_id),
        payload=payload,
    )
    return str(graph_run_id)


def enqueue_city_fact(*, graph_run_id: UUID, payload: dict[str, Any]) -> str:
    push_job(
        QUEUE_CITY_FACT,
        task="city_fact",
        graph_run_id=str(graph_run_id),
        payload=payload,
    )
    return str(graph_run_id)


def enqueue_prepare_city_pack(*, slug: str, city: str) -> str:
    import uuid

    job_id = str(uuid.uuid4())
    push_job(
        QUEUE_PREPARE_CITY_PACK,
        task="prepare_city_pack",
        graph_run_id=job_id,
        payload={"slug": slug, "city": city},
    )
    return job_id
