"""FastAPI: REST API для веб-интерфейса."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.deps import get_run_manager, get_trip_service
from api.routes import affiliate, profile, runs, trips
from config.settings import ensure_env
from db import ensure_user_profile_from_trips, init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_env()
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
        "name": "trips",
        "description": "Поездки: создание, программа, предпочтения, пересбор, HITL.",
    },
    {
        "name": "runs",
        "description": "Статус фоновых прогонов графа (polling).",
    },
    {
        "name": "profile",
        "description": "Сохранённый профиль предпочтений пользователя.",
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
        "REST API веб-интерфейса: поездки в SQLite, асинхронная сборка "
        "программы LangGraph, human-in-the-loop (утверждение / пересбор)."
    ),
    version="1.0.0",
    openapi_tags=_OPENAPI_TAGS,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trips.router, prefix="/api")
app.include_router(runs.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(affiliate.router, prefix="/api")


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health", tags=["health"])
def api_health() -> dict[str, str]:
    return {"status": "ok"}
