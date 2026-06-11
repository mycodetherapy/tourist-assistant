"""FastAPI: REST API для веб-интерфейса."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.sessions import SessionMiddleware

from api.auth.google_oauth import register_google_client
from api.auth.routes import router as auth_router
from api.deps import get_run_manager, get_trip_service
from api.rate_limit import limiter
from api.routes import affiliate, profile, runs, trips
from config.settings import cors_origins, ensure_api_env
from db import ensure_user_profile_from_trips, init_db

register_google_client()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_api_env()
    init_db()
    ensure_user_profile_from_trips()
    run_manager = get_run_manager()
    trip_service = get_trip_service()
    trip_service.recover_all_stale_buildings(
        has_active_run=run_manager.has_active_run_for_trip,
    )
    yield


_OPENAPI_TAGS = [
    {
        "name": "auth",
        "description": "Регистрация, вход, Google OAuth.",
    },
    {
        "name": "trips",
        "description": "Поездки: создание, программа, предпочтения, пересбор, HITL.",
    },
    {
        "name": "runs",
        "description": "Статус фоновых прогонов графа (polling).",
    },
    {
        "name": "profile",
        "description": "Профиль предпочтений и BYOK OpenRouter.",
    },
    {
        "name": "affiliate",
        "description": "Affiliate-метрики и синхронизация Travelpayouts (admin token).",
    },
    {
        "name": "health",
        "description": "Проверка доступности сервиса.",
    },
]

app = FastAPI(
    title="Туристический ассистент API",
    description=(
        "REST API веб-интерфейса: multi-user SaaS, поездки в SQLite, "
        "асинхронная сборка программы LangGraph, BYOK OpenRouter."
    ),
    version="2.0.0",
    openapi_tags=_OPENAPI_TAGS,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

_session_secret = os.getenv("JWT_SECRET", "dev-insecure-change-me")
app.add_middleware(SessionMiddleware, secret_key=_session_secret)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(trips.router, prefix="/api")
app.include_router(runs.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(affiliate.router, prefix="/api")


@app.get("/health", tags=["health"])
@limiter.limit("60/minute")
def health(request: Request) -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health", tags=["health"])
@limiter.limit("60/minute")
def api_health(request: Request) -> dict[str, str]:
    return {"status": "ok"}
