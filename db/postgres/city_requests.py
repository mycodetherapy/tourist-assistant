"""Заявки на города вне каталога (Postgres)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from db.models.schema import CityRequest
from db.session import get_session_factory

VALID_STATUSES = frozenset({"new", "accepted", "rejected", "built"})


def normalize_city_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def upsert_city_request(
    *,
    city_name: str,
    email: str | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    cleaned = (city_name or "").strip()
    if not cleaned:
        raise ValueError("city_name is required")
    normalized = normalize_city_name(cleaned)
    if not normalized:
        raise ValueError("city_name is required")

    now = datetime.now(timezone.utc)
    factory = get_session_factory()
    with factory() as session:
        row = session.execute(
            select(CityRequest).where(CityRequest.normalized_name == normalized)
        ).scalar_one_or_none()
        if row is None:
            row = CityRequest(
                city_name=cleaned,
                normalized_name=normalized,
                email=(email or "").strip() or None,
                user_id=user_id,
                status="new",
                request_count=1,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
        else:
            row.request_count = int(row.request_count or 0) + 1
            row.updated_at = now
            if email and not row.email:
                row.email = email.strip()
            if user_id and not row.user_id:
                row.user_id = user_id
            if row.status == "rejected":
                row.status = "new"
            session.commit()
            session.refresh(row)
        return _row_view(row)


def list_city_requests(*, status: str | None = None) -> list[dict[str, Any]]:
    factory = get_session_factory()
    with factory() as session:
        stmt = select(CityRequest).order_by(
            CityRequest.request_count.desc(), CityRequest.updated_at.desc()
        )
        if status:
            stmt = stmt.where(CityRequest.status == status)
        rows = session.execute(stmt).scalars().all()
        return [_row_view(r) for r in rows]


def set_city_request_status(
    request_id: int,
    status: str,
    *,
    note: str | None = None,
) -> dict[str, Any] | None:
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
    factory = get_session_factory()
    with factory() as session:
        row = session.get(CityRequest, request_id)
        if row is None:
            return None
        row.status = status
        row.updated_at = datetime.now(timezone.utc)
        if note is not None:
            row.note = note.strip() or None
        session.commit()
        session.refresh(row)
        return _row_view(row)


def _row_view(row: CityRequest) -> dict[str, Any]:
    return {
        "id": int(row.id),
        "city_name": row.city_name,
        "normalized_name": row.normalized_name,
        "email": row.email,
        "user_id": int(row.user_id) if row.user_id is not None else None,
        "status": row.status,
        "request_count": int(row.request_count or 1),
        "note": row.note,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
