"""Postgres helpers for self-serve OSRM prepare jobs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text, update

from db.models.schema import OsrmPrepareJob, User
from db.session import pg_session


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_job(job_id: str) -> dict[str, Any] | None:
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        return None
    with pg_session() as session:
        row = session.get(OsrmPrepareJob, uid)
        if row is None:
            return None
        return {
            "id": str(row.id),
            "user_id": int(row.user_id),
            "slug": row.slug,
            "status": row.status,
            "stage": row.stage,
            "progress": int(row.progress),
            "error": row.error,
            "counts_against_quota": bool(row.counts_against_quota),
        }


def update_job_progress(
    job_id: str,
    *,
    status: str | None = None,
    stage: str | None = None,
    progress: int | None = None,
    error: str | None = None,
    finished: bool = False,
) -> None:
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        return
    now = _utcnow()
    values: dict[str, Any] = {"updated_at": now}
    if status is not None:
        values["status"] = status
    if stage is not None:
        values["stage"] = stage
    if progress is not None:
        values["progress"] = max(0, min(100, int(progress)))
    if error is not None:
        values["error"] = error
    if finished:
        values["finished_at"] = now
    with pg_session() as session:
        session.execute(
            update(OsrmPrepareJob).where(OsrmPrepareJob.id == uid).values(**values)
        )
        session.commit()


def refund_user_quota(user_id: int) -> None:
    with pg_session() as session:
        session.execute(
            text(
                """
                UPDATE users
                SET osrm_prepare_quota_used = GREATEST(osrm_prepare_quota_used - 1, 0),
                    updated_at = NOW()
                WHERE id = :uid
                """
            ),
            {"uid": user_id},
        )
        session.commit()


def get_user_email(user_id: int) -> str | None:
    with pg_session() as session:
        row = session.get(User, user_id)
        return row.email if row else None
