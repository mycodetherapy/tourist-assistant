"""Self-serve / refresh: FO ensure → city pack → OSRM graph (concurrency 1)."""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_LOCK_KEY = "tourist:lock:osrm_prepare"
_LOCK_TTL_SEC = 60 * 60 * 2


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _acquire_lock(timeout_sec: float = 30.0) -> bool:
    from db.redis_client import get_redis

    redis = get_redis()
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if redis.set(_LOCK_KEY, "1", nx=True, ex=_LOCK_TTL_SEC):
            return True
        time.sleep(2.0)
    return False


def _release_lock() -> None:
    try:
        from db.redis_client import get_redis

        get_redis().delete(_LOCK_KEY)
    except Exception:
        logger.debug("osrm prepare unlock failed", exc_info=True)


def _fail_snippet(stdout: str, stderr: str, *, limit: int = 600) -> str:
    """Prefer docker/daemon errors; drop LangChain deprecation noise."""
    combined = "\n".join(x for x in (stderr, stdout) if x).strip()
    if not combined:
        return ""
    lines = [
        ln
        for ln in combined.splitlines()
        if "LangChainPendingDeprecationWarning" not in ln
        and "langgraph.checkpoint" not in ln
    ]
    text = "\n".join(lines).strip() or combined
    # Prefer the most actionable tail (mounts denied, Usage, Error response)
    lower = text.lower()
    for marker in ("mounts denied", "error response from daemon", "docker:", "usage:"):
        idx = lower.rfind(marker)
        if idx >= 0:
            text = text[idx:]
            break
    return text[-limit:].strip()


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    logger.info("osrm prepare: %s", " ".join(cmd))
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        err = _fail_snippet(proc.stdout or "", proc.stderr or "")
        raise RuntimeError(f"command failed ({proc.returncode}): {err or cmd}")


def run_prepare_pipeline(
    *,
    slug: str,
    federal_district: str,
    on_stage,
) -> None:
    """Run fo_ensure (if needed) + city_pack_prepare + osrm_prepare."""
    root = _repo_root()
    data_root = Path(os.getenv("TOURIST_DATA_DIR") or (root / "data"))
    host_data = (os.getenv("TOURIST_HOST_DATA_DIR") or "").strip()
    if not host_data:
        # Fallback: OSRM_HOST_DATA_CITIES=/…/data/cities → parent
        cities_host = (os.getenv("OSRM_HOST_DATA_CITIES") or "").strip()
        if cities_host.endswith("/cities"):
            host_data = cities_host[: -len("/cities")]
        elif cities_host.endswith("cities"):
            host_data = str(Path(cities_host).parent)
    env = os.environ.copy()
    env["TOURIST_DATA_DIR"] = str(data_root)
    if host_data:
        env["TOURIST_HOST_DATA_DIR"] = host_data
        logger.info(
            "osrm prepare: TOURIST_DATA_DIR=%s TOURIST_HOST_DATA_DIR=%s",
            data_root,
            host_data,
        )
    elif os.getenv("TOURIST_ASSISTANT_IN_DOCKER"):
        logger.warning(
            "TOURIST_HOST_DATA_DIR не задан — docker -v из worker на Mac/VPS "
            "скорее всего упадёт (нужен абсолютный путь хоста к data/)"
        )

    on_stage("ensure_fo", 10)
    fo_script = root / "scripts" / "fo_ensure.sh"
    if fo_script.is_file() and federal_district:
        # Не FORCE: скачает только если нет/битый
        _run(["bash", str(fo_script), federal_district], cwd=root, env=env)

    on_stage("extract", 35)
    pack_script = root / "scripts" / "city_pack_prepare.sh"
    _run(["bash", str(pack_script), slug], cwd=root, env=env)

    on_stage("osrm", 70)
    osrm_script = root / "scripts" / "osrm_prepare.sh"
    _run(["bash", str(osrm_script), slug], cwd=root, env=env)

    on_stage("finalize", 95)


def prepare_osrm_task(graph_run_id: str, payload: dict) -> None:
    from db.postgres import osrm_prepare_jobs as jobs

    job_id = str(payload.get("job_id") or graph_run_id)
    slug = str(payload.get("slug") or "").strip()
    federal_district = str(payload.get("federal_district") or "").strip()

    row = jobs.get_job(job_id)
    if row is None:
        raise ValueError(f"prepare_osrm: unknown job {job_id}")
    if not slug:
        raise ValueError("prepare_osrm: slug required")

    if not _acquire_lock(timeout_sec=120.0):
        jobs.update_job_progress(
            job_id,
            status="failed",
            stage="queued",
            progress=0,
            error="Сервер занят подготовкой другого города — попробуйте позже",
            finished=True,
        )
        if row.get("counts_against_quota"):
            jobs.refund_user_quota(int(row["user_id"]))
        return

    try:
        jobs.update_job_progress(
            job_id, status="running", stage="ensure_fo", progress=5
        )

        def on_stage(stage: str, progress: int) -> None:
            jobs.update_job_progress(job_id, stage=stage, progress=progress)

        run_prepare_pipeline(
            slug=slug,
            federal_district=federal_district,
            on_stage=on_stage,
        )
        jobs.update_job_progress(
            job_id,
            status="succeeded",
            stage="finalize",
            progress=100,
            finished=True,
        )
    except Exception as exc:
        logger.exception("prepare_osrm failed job=%s slug=%s", job_id, slug)
        err = str(exc)[:500]
        jobs.update_job_progress(
            job_id,
            status="failed",
            progress=row.get("progress") or 0,
            error=err,
            finished=True,
        )
        if row.get("counts_against_quota"):
            jobs.refund_user_quota(int(row["user_id"]))
        raise
    finally:
        _release_lock()
