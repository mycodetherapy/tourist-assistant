#!/usr/bin/env python3
"""Ночной staggered refresh FO / OSRM (раз в 14 дней, по частям).

Cron (Europe/Moscow 02:00–06:00), пример:
  15 2 * * * cd /opt/tourist-assistant && IMAGE_TAG=… \\
    docker compose -f docker-compose.prod.yml exec -T worker \\
    python scripts/osrm_nightly_refresh.py

Env:
  OSRM_REFRESH_INTERVAL_DAYS=14
  OSRM_REFRESH_CITIES_PER_NIGHT=2
  OSRM_REFRESH_FO_PER_NIGHT=1
  OSRM_REFRESH_WINDOW_START_HOUR=2
  OSRM_REFRESH_WINDOW_END_HOUR=6
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

STATE_PATH = Path(
    os.getenv("OSRM_REFRESH_STATE_PATH")
    or (os.getenv("TOURIST_DATA_DIR") or str(ROOT / "data")) + "/osrm_refresh_state.json"
)


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _in_window(now: datetime) -> bool:
    start = _env_int("OSRM_REFRESH_WINDOW_START_HOUR", 2)
    end = _env_int("OSRM_REFRESH_WINDOW_END_HOUR", 6)
    hour = now.hour
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end


def _load_state() -> dict:
    if not STATE_PATH.is_file():
        return {"fo_queue": [], "city_queue": [], "cycle_started_at": None}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"fo_queue": [], "city_queue": [], "cycle_started_at": None}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _list_fo_ids() -> list[str]:
    from config.city_catalog import load_city_pack_specs

    ids: list[str] = []
    seen: set[str] = set()
    for spec in load_city_pack_specs().values():
        fo = spec.federal_district
        if fo and fo not in seen:
            seen.add(fo)
            ids.append(fo)
    return ids


def _list_ready_slugs() -> list[str]:
    data = Path(os.getenv("TOURIST_DATA_DIR") or (ROOT / "data"))
    cities = data / "cities"
    if not cities.is_dir():
        return []
    out: list[str] = []
    for child in sorted(cities.iterdir()):
        if not child.is_dir():
            continue
        if (child / "osrm" / f"{child.name}.osrm.mldgr").is_file():
            out.append(child.name)
    return out


def _ensure_cycle(state: dict, now: datetime) -> dict:
    interval = _env_int("OSRM_REFRESH_INTERVAL_DAYS", 14)
    started = state.get("cycle_started_at")
    need_new = False
    if not started:
        need_new = True
    else:
        try:
            started_dt = datetime.fromisoformat(str(started))
            if started_dt.tzinfo is None:
                started_dt = started_dt.replace(tzinfo=timezone.utc)
            if now - started_dt >= timedelta(days=interval):
                need_new = True
        except Exception:
            need_new = True

    if need_new or (not state.get("fo_queue") and not state.get("city_queue")):
        state = {
            "fo_queue": _list_fo_ids(),
            "city_queue": _list_ready_slugs(),
            "cycle_started_at": now.isoformat(),
        }
    return state


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")

    tz = ZoneInfo(os.getenv("OSRM_REFRESH_TZ") or "Europe/Moscow")
    now = datetime.now(tz)
    if not _in_window(now) and (os.getenv("OSRM_REFRESH_FORCE") or "").strip() not in (
        "1",
        "true",
        "yes",
    ):
        print(f"outside refresh window ({now.isoformat()})")
        return 0

    # Shared lock with user prepare
    from search.osrm.prepare_job import _acquire_lock, _release_lock, run_prepare_pipeline

    if not _acquire_lock(timeout_sec=5.0):
        print("osrm prepare lock busy — skip nightly")
        return 0

    try:
        state = _ensure_cycle(_load_state(), now)
        fo_n = _env_int("OSRM_REFRESH_FO_PER_NIGHT", 1)
        city_n = _env_int("OSRM_REFRESH_CITIES_PER_NIGHT", 2)

        from config.city_catalog import get_city_pack_spec

        # FO first while queue non-empty
        for _ in range(fo_n):
            if not state.get("fo_queue"):
                break
            fo_id = state["fo_queue"].pop(0)
            print(f"refresh FO {fo_id}")
            script = ROOT / "scripts" / "fo_ensure.sh"
            env = os.environ.copy()
            env["FORCE_DOWNLOAD"] = "1"
            env["TOURIST_DATA_DIR"] = os.getenv("TOURIST_DATA_DIR") or str(ROOT / "data")
            import subprocess

            subprocess.run(
                ["bash", str(script), fo_id],
                cwd=str(ROOT),
                env=env,
                check=False,
            )

        for _ in range(city_n):
            if not state.get("city_queue"):
                break
            slug = state["city_queue"].pop(0)
            spec = get_city_pack_spec(slug)
            fo = spec.federal_district if spec else ""
            print(f"refresh city {slug} fo={fo}")

            def on_stage(stage: str, progress: int) -> None:
                print(f"  {stage} {progress}%")

            try:
                run_prepare_pipeline(
                    slug=slug,
                    federal_district=fo,
                    on_stage=on_stage,
                )
            except Exception as exc:
                print(f"  failed: {exc}", file=sys.stderr)

        _save_state(state)
        print("nightly refresh done")
        return 0
    finally:
        _release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
