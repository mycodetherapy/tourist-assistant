"""SQLite: affiliate exposure и синхронизированная статистика."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _merge_metrics_by_date(
    tp_rows: list[Any],
    local_rows: list[Any],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in tp_rows:
        day = str(row["date"])
        merged[day] = {
            "date": day,
            "local_clicks": 0,
            "clicks": int(row["clicks"] or 0),
            "bookings": int(row["bookings"] or 0),
            "revenue_rub": float(row["revenue_rub"] or 0.0),
        }
    for row in local_rows:
        day = str(row["date"])
        bucket = merged.setdefault(
            day,
            {
                "date": day,
                "local_clicks": 0,
                "clicks": 0,
                "bookings": 0,
                "revenue_rub": 0.0,
            },
        )
        bucket["local_clicks"] = int(row["clicks"] or 0)
    return [merged[day] for day in sorted(merged)]


def log_affiliate_click(
    trip_id: int,
    *,
    target_url: str,
    channel: str = "tickets",
    provider: str | None = None,
    sub_id: str | None = None,
) -> int:
    from db.connection import connect

    now = _utc_now()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO affiliate_clicks
                (trip_id, channel, provider, target_url, sub_id, clicked_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (trip_id, channel, provider, target_url, sub_id, now),
        )
        conn.commit()
        return int(cursor.lastrowid)


def log_affiliate_exposure(
    trip_id: int,
    *,
    channel: str,
    provider: str,
    provider_label: str,
    sub_id: str,
    links_count: int = 1,
    itinerary_version_id: int | None = None,
) -> int:
    from db.connection import connect

    now = _utc_now()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO affiliate_exposure
                (trip_id, itinerary_version_id, channel, provider, provider_label,
                 sub_id, links_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trip_id,
                itinerary_version_id,
                channel,
                provider,
                provider_label,
                sub_id,
                links_count,
                now,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def upsert_affiliate_stats_daily(rows: list[dict[str, Any]]) -> int:
    from db.connection import connect

    if not rows:
        return 0
    now = _utc_now()
    with connect() as conn:
        for row in rows:
            conn.execute(
                """
                INSERT INTO affiliate_stats_daily
                    (stat_date, campaign_id, campaign_name, sub_id,
                     clicks, bookings, revenue_rub, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(stat_date, campaign_id, sub_id) DO UPDATE SET
                    campaign_name = excluded.campaign_name,
                    clicks = excluded.clicks,
                    bookings = excluded.bookings,
                    revenue_rub = excluded.revenue_rub,
                    synced_at = excluded.synced_at
                """,
                (
                    row["stat_date"],
                    int(row.get("campaign_id") or 0),
                    row.get("campaign_name"),
                    str(row.get("sub_id") or ""),
                    int(row.get("clicks") or 0),
                    int(row.get("bookings") or 0),
                    float(row.get("revenue_rub") or 0.0),
                    now,
                ),
            )
        conn.commit()
    return len(rows)


def get_affiliate_metrics(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    from db.connection import connect

    with connect() as conn:
        exposure_filters = ["1=1"]
        stats_filters = ["1=1"]
        params_exposure: list[Any] = []
        params_stats: list[Any] = []

        if date_from:
            exposure_filters.append("date(created_at) >= date(?)")
            stats_filters.append("stat_date >= ?")
            params_exposure.append(date_from)
            params_stats.append(date_from)
        if date_to:
            exposure_filters.append("date(created_at) <= date(?)")
            stats_filters.append("stat_date <= ?")
            params_exposure.append(date_to)
            params_stats.append(date_to)

        exposure_where = " AND ".join(exposure_filters)
        stats_where = " AND ".join(stats_filters)

        trips_with_links = conn.execute(
            f"""
            SELECT COUNT(DISTINCT trip_id) AS cnt
            FROM affiliate_exposure
            WHERE {exposure_where}
            """,
            params_exposure,
        ).fetchone()

        click_filters = ["1=1"]
        params_clicks: list[Any] = []
        if date_from:
            click_filters.append("date(clicked_at) >= date(?)")
            params_clicks.append(date_from)
        if date_to:
            click_filters.append("date(clicked_at) <= date(?)")
            params_clicks.append(date_to)
        click_where = " AND ".join(click_filters)

        local_clicks_row = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM affiliate_clicks WHERE {click_where}",
            params_clicks,
        ).fetchone()
        local_clicks_by_date = conn.execute(
            f"""
            SELECT date(clicked_at) AS date, COUNT(*) AS clicks
            FROM affiliate_clicks
            WHERE {click_where}
            GROUP BY date(clicked_at)
            ORDER BY date ASC
            """,
            params_clicks,
        ).fetchall()

        summary_row = conn.execute(
            f"""
            SELECT
                COALESCE(SUM(clicks), 0) AS clicks,
                COALESCE(SUM(bookings), 0) AS bookings,
                COALESCE(SUM(revenue_rub), 0) AS revenue_rub
            FROM affiliate_stats_daily
            WHERE {stats_where}
            """,
            params_stats,
        ).fetchone()

        by_date = conn.execute(
            f"""
            SELECT stat_date AS date,
                   COALESCE(SUM(clicks), 0) AS clicks,
                   COALESCE(SUM(bookings), 0) AS bookings,
                   COALESCE(SUM(revenue_rub), 0) AS revenue_rub
            FROM affiliate_stats_daily
            WHERE {stats_where}
            GROUP BY stat_date
            ORDER BY stat_date ASC
            """,
            params_stats,
        ).fetchall()

        by_trip = conn.execute(
            f"""
            SELECT
                ae.trip_id,
                ae.sub_id,
                COALESCE(SUM(asd.bookings), 0) AS bookings,
                COALESCE(SUM(asd.revenue_rub), 0) AS revenue_rub
            FROM affiliate_exposure ae
            LEFT JOIN affiliate_stats_daily asd
                ON asd.sub_id = ae.sub_id
            WHERE {exposure_where.replace("created_at", "ae.created_at")}
            GROUP BY ae.trip_id, ae.sub_id
            HAVING bookings > 0 OR revenue_rub > 0
            ORDER BY revenue_rub DESC, ae.trip_id ASC
            """,
            params_exposure,
        ).fetchall()

    return {
        "period": {"from": date_from, "to": date_to},
        "summary": {
            "trips_with_affiliate_links": int(trips_with_links["cnt"] or 0),
            "local_clicks": int(local_clicks_row["cnt"] or 0),
            "clicks": int(summary_row["clicks"] or 0),
            "bookings": int(summary_row["bookings"] or 0),
            "revenue_rub": float(summary_row["revenue_rub"] or 0.0),
        },
        "by_date": _merge_metrics_by_date(by_date, local_clicks_by_date),
        "by_trip": [
            {
                "trip_id": int(row["trip_id"]),
                "sub_id": row["sub_id"],
                "bookings": int(row["bookings"] or 0),
                "revenue_rub": float(row["revenue_rub"] or 0.0),
            }
            for row in by_trip
        ],
    }
