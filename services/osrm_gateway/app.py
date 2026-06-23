"""OSRM routing gateway: proxy + lazy docker compose start."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from urllib.parse import urljoin

import httpx
from fastapi import FastAPI, Header, HTTPException, Request, Response

from config.city_catalog import get_city_pack_spec, load_city_pack_specs

logger = logging.getLogger(__name__)

app = FastAPI(title="OSRM Gateway", version="1.0.0")

ROOT = Path(__file__).resolve().parents[2]
_COMPOSE_FILE = os.getenv("COMPOSE_FILE", str(ROOT / "docker-compose.yml"))
_STARTING: set[str] = set()


def _backend_url(slug: str) -> str:
    spec = get_city_pack_spec(slug)
    if spec is not None:
        service = spec.osrm_service
    else:
        meta_path = ROOT / "data" / "cities" / slug / "meta.json"
        if meta_path.is_file():
            import json

            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            service = str(meta.get("osrm_service") or f"osrm-{slug}")
        else:
            service = f"osrm-{slug}"
    if os.getenv("TOURIST_ASSISTANT_IN_DOCKER"):
        return f"http://{service}:5000"
    port_map = {
        "kazan": os.getenv("OSRM_KAZAN_HOST_PORT", "5002"),
        "yoshkar-ola": os.getenv("OSRM_YOSHKAR_OLA_HOST_PORT", "5003"),
    }
    return f"http://127.0.0.1:{port_map.get(slug, '5000')}"


def _compose_profile(slug: str) -> str:
    spec = get_city_pack_spec(slug)
    if spec is not None:
        return spec.compose_profile
    return f"routing-city-{slug}"


def _compose_service(slug: str) -> str:
    spec = get_city_pack_spec(slug)
    if spec is not None:
        return spec.osrm_service
    return f"osrm-{slug}"


def ensure_instance(slug: str) -> None:
    if slug in _STARTING:
        return
    backend = _backend_url(slug)
    try:
        r = httpx.get(f"{backend}/route/v1/foot/0,0;0,0", timeout=2.0)
        if r.status_code in {200, 400}:
            return
    except httpx.HTTPError:
        pass

    if not os.getenv("OSRM_GATEWAY_DOCKER", "1").lower() in {"1", "true", "yes"}:
        logger.warning("OSRM backend %s unavailable; docker start disabled", slug)
        return

    _STARTING.add(slug)
    try:
        profile = _compose_profile(slug)
        service = _compose_service(slug)
        cmd = [
            "docker",
            "compose",
            "-f",
            _COMPOSE_FILE,
            "--profile",
            "routing",
            "--profile",
            profile,
            "up",
            "-d",
            service,
        ]
        logger.info("starting OSRM: %s", " ".join(cmd))
        subprocess.run(cmd, check=False, cwd=str(ROOT), timeout=120)
        for _ in range(30):
            try:
                r = httpx.get(f"{backend}/route/v1/foot/0,0;0,0", timeout=2.0)
                if r.status_code in {200, 400}:
                    return
            except httpx.HTTPError:
                pass
            import time

            time.sleep(1)
    finally:
        _STARTING.discard(slug)


def _resolve_slug(city_slug: str | None, header_slug: str | None) -> str:
    slug = (city_slug or header_slug or "").strip()
    if not slug:
        raise HTTPException(status_code=400, detail="city_slug required")
    return slug


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.api_route("/route/v1/{profile}/{coords:path}", methods=["GET"])
async def proxy_route(
    profile: str,
    coords: str,
    request: Request,
    city_slug: str | None = None,
    x_city_slug: str | None = Header(default=None, alias="X-City-Slug"),
) -> Response:
    slug = _resolve_slug(city_slug, x_city_slug)
    ensure_instance(slug)
    backend = _backend_url(slug)
    url = urljoin(backend + "/", f"route/v1/{profile}/{coords}")
    params = dict(request.query_params)
    params.pop("city_slug", None)
    try:
        upstream = httpx.get(url, params=params, timeout=float(os.getenv("OSRM_TIMEOUT", "15")))
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Response(content=upstream.content, status_code=upstream.status_code, media_type="application/json")


@app.get("/ready/{slug}")
def ready(slug: str) -> dict[str, object]:
    ensure_instance(slug)
    backend = _backend_url(slug)
    try:
        r = httpx.get(f"{backend}/route/v1/foot/0,0;0,0", timeout=3.0)
        return {"slug": slug, "backend": backend, "status_code": r.status_code}
    except httpx.HTTPError as exc:
        return {"slug": slug, "backend": backend, "error": str(exc)}


@app.get("/catalog")
def catalog() -> dict[str, object]:
    specs = load_city_pack_specs()
    return {
        "default_packs": [
            {"slug": s.slug, "service": s.osrm_service, "profile": s.compose_profile}
            for s in specs.values()
        ]
    }
