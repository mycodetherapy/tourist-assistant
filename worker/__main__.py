"""Worker entrypoint: python -m worker (JSON Redis queues)."""

from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from db.redis_client import get_redis
from services.json_job_queue import pop_job
from worker.callbacks import on_json_job_failure
from worker.tasks import (
    build_routes_task,
    city_fact_task,
    poi_fact_task,
    prepare_city_pack_task,
    prepare_osrm_task,
)


def _dispatch(job: dict[str, object]) -> None:
    task = str(job.get("task") or "")
    graph_run_id = str(job.get("graph_run_id") or "")
    payload = job.get("payload")
    if not graph_run_id or not isinstance(payload, dict):
        raise ValueError("invalid job payload")
    if task == "build_routes":
        build_routes_task(graph_run_id, payload)
        return
    if task == "city_fact":
        city_fact_task(graph_run_id, payload)
        return
    if task == "poi_fact":
        poi_fact_task(graph_run_id, payload)
        return
    if task == "prepare_city_pack":
        prepare_city_pack_task(graph_run_id, payload)
        return
    if task == "prepare_osrm":
        prepare_osrm_task(graph_run_id, payload)
        return
    raise ValueError(f"unknown task: {task}")


def main() -> int | None:
    if not os.getenv("REDIS_URL", "").strip():
        print(
            "REDIS_URL не задан. Добавьте в .env, например:\n"
            "  REDIS_URL=redis://localhost:6380/0",
            file=sys.stderr,
        )
        return 1
    if not os.getenv("DATABASE_URL", "").strip():
        print("DATABASE_URL обязателен для worker.", file=sys.stderr)
        return 1

    get_redis()
    print("JSON worker: listening on tourist:queue:*", flush=True)
    while True:
        item = pop_job(timeout_sec=5)
        if item is None:
            continue
        _queue_name, job = item
        task = str(job.get("task") or "")
        graph_run_id = str(job.get("graph_run_id") or "")
        payload = job.get("payload")
        if not isinstance(payload, dict):
            continue
        try:
            _dispatch(job)
        except Exception as exc:
            on_json_job_failure(
                task=task,
                graph_run_id=graph_run_id,
                payload=payload,
                exc=exc,
            )
            print(f"job failed {task} {graph_run_id}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main() or 0)
