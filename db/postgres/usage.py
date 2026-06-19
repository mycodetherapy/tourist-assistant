"""Usage / billing events (Postgres)."""

from __future__ import annotations

import uuid
from typing import Any

from db.models.schema import UsageEvent
from db.postgres._helpers import utc_now
from db.session import pg_session


def record_usage_event(
    *,
    user_id: int,
    source: str,
    trip_id: int | None = None,
    graph_run_id: uuid.UUID | str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    cost_usd: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> int:
    run_uuid: uuid.UUID | None = None
    if graph_run_id is not None:
        run_uuid = (
            graph_run_id
            if isinstance(graph_run_id, uuid.UUID)
            else uuid.UUID(str(graph_run_id))
        )
    with pg_session() as session:
        row = UsageEvent(
            user_id=user_id,
            trip_id=trip_id,
            graph_run_id=run_uuid,
            source=source,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            created_at=utc_now(),
        )
        session.add(row)
        session.flush()
        return int(row.id)
