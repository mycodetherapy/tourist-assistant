"""Синхронизация статистики бронирований из Travelpayouts."""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

import requests

from db.affiliate_repository import upsert_affiliate_stats_daily

STATS_QUERY_URL = "https://api.travelpayouts.com/statistics/v1/execute_query"
FINANCE_ACTIONS_URL = (
    "https://api.travelpayouts.com/finance/v2/get_user_actions_affecting_balance"
)
STATS_TIMEOUT = 30
_PAGE_LIMIT = 10_000


def _affiliate_api_token() -> str:
    return os.getenv("TRAVELPAYOUTS_API_KEY", "").strip()


class AffiliateSyncError(RuntimeError):
    pass


def _headers(token: str) -> dict[str, str]:
    return {
        "X-Access-Token": token,
        "Content-Type": "application/json",
    }


def _execute_statistics_query(token: str, body: dict[str, Any]) -> list[dict[str, Any]]:
    """POST statistics/v1/execute_query с пагинацией."""
    rows: list[dict[str, Any]] = []
    offset = int(body.get("offset") or 0)
    limit = min(int(body.get("limit") or _PAGE_LIMIT), _PAGE_LIMIT)

    while True:
        page_body = {**body, "offset": offset, "limit": limit}
        try:
            response = requests.post(
                STATS_QUERY_URL,
                json=page_body,
                headers=_headers(token),
                timeout=STATS_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise AffiliateSyncError(
                f"Statistics API ({STATS_QUERY_URL}): {exc}"
            ) from exc

        batch = payload.get("results") or []
        if not isinstance(batch, list):
            break
        rows.extend(row for row in batch if isinstance(row, dict))

        total_rows = int(payload.get("total_rows") or len(rows))
        offset += len(batch)
        if not batch or offset >= total_rows:
            break

    return rows


def _fetch_statistics_rows(
    token: str,
    *,
    date_from: date,
    date_to: date,
    event_type: str,
    fields: list[str],
) -> list[dict[str, Any]]:
    body = {
        "fields": fields,
        "filters": [
            {"field": "type", "op": "eq", "value": event_type},
            {"field": "date", "op": "ge", "value": date_from.isoformat()},
            {"field": "date", "op": "le", "value": date_to.isoformat()},
        ],
        "sort": [{"field": "date", "order": "asc"}],
        "offset": 0,
        "limit": _PAGE_LIMIT,
    }
    return _execute_statistics_query(token, body)


def _aggregate_statistics_rows(
    click_rows: list[dict[str, Any]],
    action_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    aggregated: dict[tuple[str, int, str], dict[str, Any]] = {}

    def bucket(row: dict[str, Any]) -> dict[str, Any]:
        stat_date = str(row.get("date") or "")[:10]
        campaign = int(row.get("campaign_id") or 0)
        sub_id = str(row.get("sub_id") or "")
        key = (stat_date, campaign, sub_id)
        return aggregated.setdefault(
            key,
            {
                "stat_date": stat_date,
                "campaign_id": campaign,
                "campaign_name": None,
                "sub_id": sub_id,
                "clicks": 0,
                "bookings": 0,
                "revenue_rub": 0.0,
            },
        )

    for row in click_rows:
        if not str(row.get("date") or "").strip():
            continue
        bucket(row)["clicks"] += 1

    for row in action_rows:
        if not str(row.get("date") or "").strip():
            continue
        state = str(row.get("state") or "").lower()
        if state and state not in ("paid", "processing"):
            continue
        item = bucket(row)
        item["bookings"] += 1
        item["revenue_rub"] += float(row.get("paid_profit_rub") or 0.0)

    return [
        row
        for row in aggregated.values()
        if row["stat_date"]
        and (row["clicks"] or row["bookings"] or row["revenue_rub"])
    ]


def _fetch_finance_fallback(
    token: str,
    *,
    date_from: date,
    date_to: date,
) -> list[dict[str, Any]]:
    """Fallback: finance/v2, если Statistics API недоступен."""
    rows: list[dict[str, Any]] = []
    offset = 0
    limit = 300

    while True:
        params = {
            "currency": "rub",
            "from": date_from.isoformat(),
            "until": date_to.isoformat(),
            "offset": offset,
            "limit": limit,
        }
        try:
            response = requests.get(
                FINANCE_ACTIONS_URL,
                params=params,
                headers={"X-Access-Token": token},
                timeout=STATS_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise AffiliateSyncError(
                f"Finance API ({FINANCE_ACTIONS_URL}): {exc}"
            ) from exc

        actions = payload.get("actions") or []
        if not isinstance(actions, list) or not actions:
            break

        for action in actions:
            if not isinstance(action, dict):
                continue
            state = str(action.get("action_state") or "").lower()
            if state and state not in ("paid", "processing"):
                continue
            booked_at = str(action.get("booked_at") or action.get("updated_at") or "")
            stat_date = booked_at[:10]
            if not stat_date:
                continue
            campaign = int(action.get("campaign_id") or 0)
            rows.append(
                {
                    "stat_date": stat_date,
                    "campaign_id": campaign,
                    "campaign_name": None,
                    "sub_id": "",
                    "clicks": 0,
                    "bookings": 1,
                    "revenue_rub": float(action.get("profit") or 0.0),
                }
            )

        count = int(payload.get("count") or 0)
        offset += len(actions)
        if offset >= count:
            break

    aggregated: dict[tuple[str, int, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["stat_date"], row["campaign_id"], row["sub_id"])
        bucket = aggregated.setdefault(key, {**row, "bookings": 0, "revenue_rub": 0.0})
        bucket["bookings"] += 1
        bucket["revenue_rub"] += row["revenue_rub"]

    return list(aggregated.values())


def fetch_booking_stats(
    *,
    date_from: date,
    date_to: date | None = None,
    campaign_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Загружает клики (redirect) и брони (action) из Statistics API.
    Без токена — пустой список.
    """
    token = _affiliate_api_token()
    if not token:
        return []

    end = date_to or date.today()
    action_fields = [
        "action_id",
        "sub_id",
        "date",
        "campaign_id",
        "paid_profit_rub",
        "state",
    ]
    click_fields = ["sub_id", "date", "campaign_id"]

    try:
        click_rows = _fetch_statistics_rows(
            token,
            date_from=date_from,
            date_to=end,
            event_type="redirect",
            fields=click_fields,
        )
        action_rows = _fetch_statistics_rows(
            token,
            date_from=date_from,
            date_to=end,
            event_type="action",
            fields=action_fields,
        )
        rows = _aggregate_statistics_rows(click_rows, action_rows)
    except AffiliateSyncError as exc:
        print(f"  → affiliate stats sync: {exc}; пробуем finance API")
        rows = _fetch_finance_fallback(token, date_from=date_from, date_to=end)

    if campaign_id is not None:
        rows = [row for row in rows if int(row.get("campaign_id") or 0) == campaign_id]

    return rows


def sync_affiliate_stats(*, days: int = 30) -> int:
    """Синхронизирует статистику за последние N дней. Возвращает число строк."""
    start = date.today() - timedelta(days=max(1, days))
    rows = fetch_booking_stats(date_from=start)
    if not rows:
        print(
            "  → affiliate stats sync: в Travelpayouts за период нет redirect/action "
            "(клики без marker= в URL не учитываются; local_clicks — в /api/affiliate/metrics)"
        )
    return upsert_affiliate_stats_daily(rows)
