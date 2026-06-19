"""Redis client for job queue and rate limits."""

from __future__ import annotations

import os
from functools import lru_cache

import redis

# RQ требует binary mode (decode_responses=False) — иначе задачи не попадают в очередь.


def get_redis_url() -> str | None:
    raw = os.getenv("REDIS_URL", "").strip()
    return raw or None


def is_redis_enabled() -> bool:
    return get_redis_url() is not None


@lru_cache(maxsize=1)
def get_redis() -> redis.Redis:
    url = get_redis_url()
    if not url:
        raise RuntimeError("REDIS_URL is not set")
    return redis.from_url(url, decode_responses=False)


def clear_redis_cache() -> None:
    get_redis.cache_clear()  # type: ignore[attr-defined]
