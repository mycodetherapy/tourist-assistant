"""Audit events (Postgres)."""

from __future__ import annotations

from typing import Any

from db.models.schema import AuditEvent
from db.postgres._helpers import utc_now
from db.session import pg_session


def record_audit_event(
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    user_id: int | None = None,
    metadata: dict[str, Any] | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> int:
    with pg_session() as session:
        row = AuditEvent(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata,
            ip=ip,
            user_agent=user_agent,
            created_at=utc_now(),
        )
        session.add(row)
        session.flush()
        return int(row.id)
