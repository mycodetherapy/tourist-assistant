"""SaaS audit/usage helpers (Postgres only)."""

from __future__ import annotations

import uuid
from typing import Any

from db.session import is_postgres_enabled


def audit(
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    user_id: int | None = None,
    metadata: dict[str, Any] | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    if not is_postgres_enabled():
        return
    from db.postgres import audit as pg_audit

    pg_audit.record_audit_event(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        metadata=metadata,
        ip=ip,
        user_agent=user_agent,
    )


def usage_from_graph_run(
    *,
    user_id: int,
    trip_id: int,
    scope: str,
    graph_run_id: str | uuid.UUID | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    cost_usd: float | None = None,
) -> None:
    if not is_postgres_enabled():
        return
    from db.postgres import usage as pg_usage

    pg_usage.record_usage_event(
        user_id=user_id,
        trip_id=trip_id,
        graph_run_id=graph_run_id,
        source=f"graph:{scope}",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
    )
