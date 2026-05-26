"""LangSmith: теги и metadata для прогонов."""

from __future__ import annotations

import os
from typing import Any


def langsmith_enabled() -> bool:
    return os.getenv("LANGCHAIN_TRACING_V2", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def run_metadata(
    *,
    trip_id: int | None = None,
    agent: str | None = None,
    rebuild_scope: str | None = None,
    retry_count: int | None = None,
) -> dict[str, Any]:
    """Metadata для invoke/config LangGraph."""
    meta: dict[str, Any] = {"project": os.getenv("LANGCHAIN_PROJECT", "tourist-assistant")}
    tags: list[str] = []
    if agent:
        tags.append(f"agent:{agent}")
    if rebuild_scope:
        tags.append(f"scope:{rebuild_scope}")
    if trip_id is not None:
        tags.append(f"trip:{trip_id}")
    if retry_count is not None:
        tags.append(f"retry:{retry_count}")
    if tags:
        meta["tags"] = tags
    return meta


def invoke_config(
    trip_id: int,
    *,
    agent: str | None = None,
    rebuild_scope: str | None = None,
    retry_count: int = 0,
) -> dict[str, Any]:
    """config для app.invoke с thread_id и metadata."""
    return {
        "configurable": {"thread_id": f"trip-{trip_id}"},
        "metadata": run_metadata(
            trip_id=trip_id,
            agent=agent,
            rebuild_scope=rebuild_scope,
            retry_count=retry_count,
        ),
    }
