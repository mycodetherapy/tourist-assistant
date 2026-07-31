#!/usr/bin/env python3
"""Консольная статистика пользователей и активности (Postgres).

Примеры:
  python3 scripts/admin_stats.py summary
  python3 scripts/admin_stats.py registrations --days 30
  python3 scripts/admin_stats.py logins --days 30
  python3 scripts/admin_stats.py online --minutes 5
  python3 scripts/admin_stats.py activity --limit 20
  python3 scripts/admin_stats.py user --email user@example.com
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from db.session import get_engine, is_postgres_enabled  # noqa: E402


def _require_db() -> None:
    if not is_postgres_enabled():
        print("DATABASE_URL не задан в .env", file=sys.stderr)
        sys.exit(1)


def _fetch_all(sql: str, **params: Any) -> list[dict[str, Any]]:
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(sql), params)
        return [dict(row._mapping) for row in result]


def _fetch_one(sql: str, **params: Any) -> dict[str, Any] | None:
    rows = _fetch_all(sql, **params)
    return rows[0] if rows else None


def _print_daily_table(title: str, rows: list[dict[str, Any]]) -> None:
    print(f"\n{title}")
    if not rows:
        print("  (нет данных)")
        return
    print(f"  {'День':<12} {'Кол-во':>8}")
    print(f"  {'-' * 12} {'-' * 8}")
    for row in rows:
        day = str(row.get("day") or "")[:10]
        count = int(row.get("count") or 0)
        print(f"  {day:<12} {count:>8}")


def cmd_summary(_args: argparse.Namespace) -> None:
    row = _fetch_one(
        """
        SELECT
          (SELECT COUNT(*) FROM users) AS users_total,
          (SELECT COUNT(*) FROM users
           WHERE created_at >= date_trunc('day', NOW())) AS users_today,
          (SELECT COUNT(*) FROM users
           WHERE created_at >= NOW() - INTERVAL '7 days') AS users_week,
          (SELECT COUNT(*) FROM audit_events
           WHERE action = 'user.login'
             AND created_at >= date_trunc('day', NOW())) AS logins_today,
          (SELECT COUNT(DISTINCT user_id) FROM audit_events
           WHERE user_id IS NOT NULL
             AND created_at >= NOW() - INTERVAL '1 day') AS dau,
          (SELECT COUNT(*) FROM users
           WHERE last_seen_at >= NOW() - INTERVAL '5 minutes') AS online_5m,
          (SELECT COUNT(*) FROM trips) AS trips_total,
          (SELECT COUNT(*) FROM graph_runs) AS runs_total
        """
    )
    if row is None:
        print("Нет данных")
        return
    print("Сводка")
    print(f"  Пользователей всего:     {row['users_total']}")
    print(f"  Регистраций сегодня:     {row['users_today']}")
    print(f"  Регистраций за 7 дней:   {row['users_week']}")
    print(f"  Логинов сегодня:         {row['logins_today']}")
    print(f"  Активных за 24ч (DAU):   {row['dau']}")
    print(f"  «Онлайн» (~5 мин):       {row['online_5m']}")
    print(f"  Поездок всего:           {row['trips_total']}")
    print(f"  Прогонов графа всего:    {row['runs_total']}")


def cmd_registrations(args: argparse.Namespace) -> None:
    rows = _fetch_all(
        """
        SELECT date_trunc('day', created_at) AS day, COUNT(*) AS count
        FROM users
        WHERE created_at >= NOW() - make_interval(days => :days)
        GROUP BY 1
        ORDER BY 1 DESC
        """,
        days=args.days,
    )
    _print_daily_table(f"Регистрации за {args.days} дней", rows)


def cmd_logins(args: argparse.Namespace) -> None:
    rows = _fetch_all(
        """
        SELECT date_trunc('day', created_at) AS day, COUNT(*) AS count
        FROM audit_events
        WHERE action = 'user.login'
          AND created_at >= NOW() - make_interval(days => :days)
        GROUP BY 1
        ORDER BY 1 DESC
        """,
        days=args.days,
    )
    _print_daily_table(f"Логины за {args.days} дней", rows)


def cmd_online(args: argparse.Namespace) -> None:
    rows = _fetch_all(
        """
        SELECT
          u.id,
          u.email,
          u.last_seen_at,
          (SELECT COUNT(*) FROM trips t WHERE t.user_id = u.id) AS trips,
          (SELECT COUNT(*) FROM graph_runs gr WHERE gr.user_id = u.id) AS runs
        FROM users u
        WHERE u.last_seen_at >= NOW() - make_interval(mins => :minutes)
        ORDER BY u.last_seen_at DESC
        """,
        minutes=args.minutes,
    )
    title = f"«Онлайн» (активность за {args.minutes} мин)"
    print(f"\n{title}")
    if not rows:
        print("  (никого)")
        return
    print(
        f"  {'id':<6} {'email':<32} {'last_seen_at':<26} {'trips':>6} {'runs':>6}"
    )
    print(f"  {'-' * 6} {'-' * 32} {'-' * 26} {'-' * 6} {'-' * 6}")
    for row in rows:
        seen = str(row.get("last_seen_at") or "")[:19]
        print(
            f"  {int(row['id']):<6} "
            f"{str(row['email'])[:32]:<32} "
            f"{seen:<26} "
            f"{int(row['trips']):>6} "
            f"{int(row['runs']):>6}"
        )


def cmd_activity(args: argparse.Namespace) -> None:
    rows = _fetch_all(
        """
        SELECT
          u.id,
          u.email,
          u.created_at,
          u.last_seen_at,
          (SELECT COUNT(*) FROM trips t WHERE t.user_id = u.id) AS trips,
          (SELECT COUNT(*) FROM graph_runs gr WHERE gr.user_id = u.id) AS runs,
          (SELECT COUNT(*) FROM audit_events ae
           WHERE ae.user_id = u.id AND ae.action = 'user.login') AS logins,
          (SELECT COALESCE(SUM(ue.total_tokens), 0) FROM usage_events ue
           WHERE ue.user_id = u.id) AS tokens
        FROM users u
        ORDER BY u.last_seen_at DESC NULLS LAST, u.created_at DESC
        LIMIT :limit
        """,
        limit=args.limit,
    )
    print(f"\nПользователи (топ {args.limit} по last_seen_at)")
    if not rows:
        print("  (нет пользователей)")
        return
    print(
        f"  {'id':<6} {'email':<28} {'trips':>6} {'runs':>6} "
        f"{'logins':>7} {'tokens':>8} last_seen"
    )
    print(f"  {'-' * 6} {'-' * 28} {'-' * 6} {'-' * 6} {'-' * 7} {'-' * 8} {'-' * 19}")
    for row in rows:
        seen = str(row.get("last_seen_at") or "—")[:19]
        print(
            f"  {int(row['id']):<6} "
            f"{str(row['email'])[:28]:<28} "
            f"{int(row['trips']):>6} "
            f"{int(row['runs']):>6} "
            f"{int(row['logins']):>7} "
            f"{int(row['tokens']):>8} "
            f"{seen}"
        )

    events = _fetch_all(
        """
        SELECT ae.created_at, ae.action, ae.entity_type, ae.entity_id,
               u.email, ae.metadata_json
        FROM audit_events ae
        LEFT JOIN users u ON u.id = ae.user_id
        ORDER BY ae.created_at DESC
        LIMIT :limit
        """,
        limit=args.limit,
    )
    print(f"\nПоследние события audit (limit {args.limit})")
    if not events:
        print("  (нет событий)")
        return
    for ev in events:
        ts = str(ev.get("created_at") or "")[:19]
        email = str(ev.get("email") or "—")
        meta = ev.get("metadata_json")
        meta_s = f" {meta}" if meta else ""
        print(
            f"  {ts}  {email:<28}  {ev['action']:<18} "
            f"{ev['entity_type']}:{ev['entity_id']}{meta_s}"
        )


def cmd_user(args: argparse.Namespace) -> None:
    if args.email:
        row = _fetch_one(
            """
            SELECT id, email, created_at, updated_at, last_seen_at, google_sub
            FROM users WHERE lower(email) = lower(:email)
            """,
            email=args.email.strip(),
        )
    elif args.user_id is not None:
        row = _fetch_one(
            """
            SELECT id, email, created_at, updated_at, last_seen_at, google_sub
            FROM users WHERE id = :user_id
            """,
            user_id=args.user_id,
        )
    else:
        print("Укажите --email или --id", file=sys.stderr)
        sys.exit(1)

    if row is None:
        print("Пользователь не найден", file=sys.stderr)
        sys.exit(1)

    user_id = int(row["id"])
    print(f"Пользователь #{user_id}: {row['email']}")
    print(f"  created_at:   {row['created_at']}")
    print(f"  last_seen_at: {row.get('last_seen_at') or '—'}")
    print(f"  google:       {'да' if row.get('google_sub') else 'нет'}")

    stats = _fetch_one(
        """
        SELECT
          (SELECT COUNT(*) FROM trips WHERE user_id = :uid) AS trips,
          (SELECT COUNT(*) FROM graph_runs WHERE user_id = :uid) AS runs,
          (SELECT COUNT(*) FROM audit_events
           WHERE user_id = :uid AND action = 'user.login') AS logins,
          (SELECT COALESCE(SUM(total_tokens), 0) FROM usage_events
           WHERE user_id = :uid) AS tokens,
          (SELECT COALESCE(SUM(cost_usd), 0) FROM usage_events
           WHERE user_id = :uid) AS cost_usd
        """,
        uid=user_id,
    )
    if stats:
        print(f"  поездок:      {stats['trips']}")
        print(f"  прогонов:     {stats['runs']}")
        print(f"  логинов:      {stats['logins']}")
        print(f"  tokens:       {stats['tokens']}")
        print(f"  cost_usd:     {stats['cost_usd']}")

    trips = _fetch_all(
        """
        SELECT id, city, dates, status, created_at, updated_at
        FROM trips WHERE user_id = :uid
        ORDER BY updated_at DESC
        LIMIT 10
        """,
        uid=user_id,
    )
    print("\n  Поездки (до 10):")
    if not trips:
        print("    (нет)")
    else:
        for t in trips:
            print(
                f"    #{t['id']} {t['city']} ({t['dates']}) "
                f"status={t['status']} updated={str(t['updated_at'])[:19]}"
            )

    events = _fetch_all(
        """
        SELECT created_at, action, entity_type, entity_id, metadata_json
        FROM audit_events
        WHERE user_id = :uid
        ORDER BY created_at DESC
        LIMIT 20
        """,
        uid=user_id,
    )
    print("\n  Audit (последние 20):")
    if not events:
        print("    (нет)")
    else:
        for ev in events:
            ts = str(ev.get("created_at") or "")[:19]
            meta = ev.get("metadata_json")
            meta_s = f" {meta}" if meta else ""
            print(f"    {ts}  {ev['action']}  {ev['entity_type']}:{ev['entity_id']}{meta_s}")


def main() -> None:
    _require_db()
    parser = argparse.ArgumentParser(
        description="Статистика пользователей tourist-assistant (Postgres)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("summary", help="Сводка KPI").set_defaults(func=cmd_summary)

    p_reg = sub.add_parser("registrations", help="Регистрации по дням")
    p_reg.add_argument("--days", type=int, default=30)
    p_reg.set_defaults(func=cmd_registrations)

    p_log = sub.add_parser("logins", help="Логины по дням")
    p_log.add_argument("--days", type=int, default=30)
    p_log.set_defaults(func=cmd_logins)

    p_on = sub.add_parser("online", help="Недавно активные пользователи")
    p_on.add_argument("--minutes", type=int, default=5)
    p_on.set_defaults(func=cmd_online)

    p_act = sub.add_parser("activity", help="Активность пользователей и audit")
    p_act.add_argument("--limit", type=int, default=20)
    p_act.set_defaults(func=cmd_activity)

    p_user = sub.add_parser("user", help="Детали одного пользователя")
    p_user.add_argument("--email", type=str, default=None)
    p_user.add_argument("--id", dest="user_id", type=int, default=None)
    p_user.set_defaults(func=cmd_user)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
