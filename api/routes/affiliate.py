"""Affiliate-метрики (admin)."""

from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException, Query

from api.schemas.responses import AffiliateMetricsResponse
from db.affiliate_repository import get_affiliate_metrics
from services.affiliate_sync import sync_affiliate_stats

router = APIRouter(prefix="/affiliate", tags=["affiliate"])


def _require_admin(authorization: str | None) -> None:
    token = os.getenv("AFFILIATE_ADMIN_TOKEN", "").strip()
    if not token:
        raise HTTPException(
            status_code=503,
            detail="AFFILIATE_ADMIN_TOKEN не задан",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Требуется Bearer token")
    if authorization.removeprefix("Bearer ").strip() != token:
        raise HTTPException(status_code=403, detail="Неверный token")


@router.get("/metrics", response_model=AffiliateMetricsResponse)
def affiliate_metrics(
    date_from: str | None = Query(None, description="YYYY-MM-DD"),
    date_to: str | None = Query(None, description="YYYY-MM-DD"),
    authorization: str | None = Header(None),
) -> AffiliateMetricsResponse:
    """Сводка affiliate: exposure локально, доход из синка Travelpayouts."""
    _require_admin(authorization)
    payload = get_affiliate_metrics(date_from=date_from, date_to=date_to)
    return AffiliateMetricsResponse.model_validate(payload)


@router.post("/sync")
def affiliate_sync(
    days: int = Query(30, ge=1, le=365),
    authorization: str | None = Header(None),
) -> dict[str, int | str]:
    """Подтянуть статистику бронирований из Travelpayouts за N дней."""
    _require_admin(authorization)
    count = sync_affiliate_stats(days=days)
    return {"synced_rows": count, "days": days}
