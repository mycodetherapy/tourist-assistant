"""Эфемерный osrm-routed: один граф на время HTTP /route (для VPS 4 ГБ).

Worker в Docker: mount /var/run/docker.sock + OSRM_HOST_DATA_CITIES
(абсолютный путь хоста к data/cities) + OSRM_DOCKER_NETWORK (сеть compose).
Управление контейнером — Docker Engine API по unix-сокету (без docker CLI в образе).
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import httpx

from models.routes import GeoPoint
from search.osrm.client import OsrmRouteResult, fetch_foot_route

logger = logging.getLogger(__name__)

_CONTAINER = "osrm-ephemeral"
_LOCK_PATH = Path(os.getenv("OSRM_EPHEMERAL_LOCK", "/tmp/tourist-osrm-ephemeral.lock"))
_DEFAULT_IMAGE = "ghcr.io/project-osrm/osrm-backend:v5.27.1"
_DOCKER_SOCK = os.getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
_API = "http://docker"


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def ephemeral_enabled() -> bool:
    mode = _env("OSRM_MODE", "http").lower()
    return mode == "ephemeral" or _env("OSRM_EPHEMERAL") in ("1", "true", "yes")


def _api_prefix() -> str:
    raw = _env("DOCKER_API_VERSION", "v1.43") or "v1.43"
    if not raw.startswith("v"):
        raw = f"v{raw}"
    return f"/{raw}"


def _host_cities_dir() -> Path:
    raw = _env("OSRM_HOST_DATA_CITIES")
    if raw:
        return Path(raw)
    from config.city_catalog import data_root

    return data_root() / "cities"


def _graph_ready_on_host(slug: str) -> bool:
    # OSRM_HOST_DATA_CITIES — путь хоста (для docker bind); внутри worker
    # граф читаем с зеркала volume (TOURIST_DATA_DIR / data_root).
    candidates: list[Path] = []
    data_dir = _env("TOURIST_DATA_DIR")
    if data_dir:
        candidates.append(Path(data_dir) / "cities")
    try:
        from config.city_catalog import data_root

        candidates.append(data_root() / "cities")
    except Exception:
        pass
    host = _env("OSRM_HOST_DATA_CITIES")
    if host:
        candidates.append(Path(host))
    for root in candidates:
        if (root / slug / "osrm" / f"{slug}.osrm.mldgr").is_file():
            return True
    return False


def _docker_client() -> httpx.Client:
    sock = _DOCKER_SOCK
    if sock.startswith("unix://"):
        uds = sock.removeprefix("unix://")
        transport = httpx.HTTPTransport(uds=uds)
        return httpx.Client(transport=transport, base_url=_API, timeout=60.0)
    base = sock.replace("tcp://", "http://")
    return httpx.Client(base_url=base, timeout=60.0)


def _stop_ephemeral(client: httpx.Client) -> None:
    prefix = _api_prefix()
    try:
        client.delete(
            f"{prefix}/containers/{_CONTAINER}", params={"force": "true"}
        )
    except Exception:
        logger.debug("ephemeral stop ignored", exc_info=True)


def _start_ephemeral(client: httpx.Client, *, slug: str) -> bool:
    cities_host = str(_host_cities_dir())
    image = _env("OSRM_IMAGE", _DEFAULT_IMAGE) or _DEFAULT_IMAGE
    network = _env("OSRM_DOCKER_NETWORK")
    graph_in_container = f"/data/{slug}/osrm/{slug}.osrm"
    prefix = _api_prefix()

    host_config: dict = {
        "Binds": [f"{cities_host}:/data:ro"],
        "AutoRemove": True,
    }
    if network:
        host_config["NetworkMode"] = network

    body = {
        "Image": image,
        "Cmd": ["osrm-routed", "--algorithm", "mld", graph_in_container],
        "HostConfig": host_config,
    }

    _stop_ephemeral(client)
    created = client.post(
        f"{prefix}/containers/create",
        params={"name": _CONTAINER},
        content=json.dumps(body),
        headers={"Content-Type": "application/json"},
    )
    if created.status_code not in (201, 200):
        logger.warning(
            "ephemeral create failed: %s %s",
            created.status_code,
            created.text[:500],
        )
        return False
    cid = created.json().get("Id") or _CONTAINER
    started = client.post(f"{prefix}/containers/{cid}/start")
    if started.status_code not in (204, 200):
        logger.warning(
            "ephemeral start failed: %s %s",
            started.status_code,
            started.text[:500],
        )
        _stop_ephemeral(client)
        return False
    return True


def _wait_ready(base_url: str, *, timeout_s: float = 45.0) -> bool:
    deadline = time.monotonic() + timeout_s
    probe = f"{base_url.rstrip('/')}/route/v1/foot/0,0;0.001,0.001?overview=false"
    while time.monotonic() < deadline:
        try:
            with httpx.Client(timeout=2.0) as client:
                client.get(probe)
                return True
        except Exception:
            time.sleep(0.4)
    return False


def fetch_foot_route_ephemeral(
    points: list[GeoPoint],
    *,
    slug: str,
    timeout_s: float = 8.0,
) -> OsrmRouteResult | None:
    """Поднять osrm-routed для slug, запросить маршрут, остановить контейнер."""
    if len(points) < 2 or not slug:
        return None
    if not _graph_ready_on_host(slug):
        logger.info("ephemeral OSRM: no graph for slug=%s", slug)
        return None

    route_base = _env("OSRM_EPHEMERAL_URL", f"http://{_CONTAINER}:5000")

    _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOCK_PATH, "a+", encoding="utf-8") as lock_file:
        try:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        except Exception:
            logger.warning("ephemeral OSRM: flock unavailable, continuing without lock")

        try:
            with _docker_client() as docker:
                if not _start_ephemeral(docker, slug=slug):
                    return None
                try:
                    if not _wait_ready(route_base):
                        logger.warning(
                            "ephemeral OSRM: timeout waiting for %s", route_base
                        )
                        return None
                    return fetch_foot_route(
                        points, base_url=route_base, timeout_s=timeout_s
                    )
                finally:
                    _stop_ephemeral(docker)
        except Exception:
            logger.warning("ephemeral OSRM failed", exc_info=True)
            return None
