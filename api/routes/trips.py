"""Маршруты поездок."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_run_manager, get_trip_service
from api.schemas.requests import CreateTripRequest, ReviewRequest, StartRunRequest
from api.schemas.responses import (
    CreateTripResponse,
    ProgramResponse,
    ReviewResponse,
    TripDetailResponse,
    TripSummaryResponse,
)
from onboarding.preferences import TripPreferences
from services.run_manager import RunManager
from services.trip_service import TripService

router = APIRouter(prefix="/trips", tags=["trips"])


@router.get("", response_model=list[TripSummaryResponse])
def list_trips(
    service: TripService = Depends(get_trip_service),
    run_manager: RunManager = Depends(get_run_manager),
) -> list[TripSummaryResponse]:
    for summary in service.list_all_trips():
        if summary.status == "building":
            service.recover_stale_building(
                summary.id,
                has_active_run=run_manager.has_active_run_for_trip(summary.id),
            )
    return [
        TripSummaryResponse(
            id=t.id,
            city=t.city,
            dates=t.dates,
            origin_city=t.origin_city,
            status=t.status,
            updated_at=t.updated_at,
        )
        for t in service.list_all_trips()
    ]


@router.post("", response_model=CreateTripResponse, status_code=201)
def create_trip(
    body: CreateTripRequest,
    service: TripService = Depends(get_trip_service),
    run_manager: RunManager = Depends(get_run_manager),
) -> CreateTripResponse:
    trip_id = service.create_new_trip(
        city=body.city,
        dates=body.dates,
        origin_city=body.origin_city,
        user_query=body.user_query,
        preferences=body.preferences,
    )
    run_id: str | None = None
    if body.start_run:
        details = service.get_trip_details(trip_id)
        assert details is not None
        trip = details.trip
        state = service.build_initial_state(
            trip_id=trip_id,
            city=trip["city"],
            dates=trip["dates"],
            origin_city=trip["origin_city"],
            search_context=service.apply_preferences(body.preferences),
            preferences_dict=body.preferences.model_dump(),
            rebuild_scope="full",
            user_message=trip.get("user_query") or body.user_query,
            review_mode="deferred",
        )
        run_id = run_manager.start_run(state)
    return CreateTripResponse(trip_id=trip_id, run_id=run_id)


@router.get("/{trip_id}", response_model=TripDetailResponse)
def get_trip(
    trip_id: int,
    service: TripService = Depends(get_trip_service),
    run_manager: RunManager = Depends(get_run_manager),
) -> TripDetailResponse:
    service.recover_stale_building(
        trip_id,
        has_active_run=run_manager.has_active_run_for_trip(trip_id),
    )
    details = service.get_trip_details(trip_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
    trip = details.trip
    return TripDetailResponse(
        id=int(trip["id"]),
        city=trip["city"],
        dates=trip["dates"],
        origin_city=trip["origin_city"],
        user_query=trip.get("user_query"),
        status=trip["status"],
        created_at=trip["created_at"],
        updated_at=trip["updated_at"],
    )


@router.get("/{trip_id}/program", response_model=ProgramResponse)
def get_program(
    trip_id: int,
    service: TripService = Depends(get_trip_service),
) -> ProgramResponse:
    details = service.get_trip_details(trip_id)
    if details is None or details.latest_itinerary is None:
        raise HTTPException(status_code=404, detail="Программа не найдена")
    latest = details.latest_itinerary
    program = service.parse_program(latest["program"])
    return ProgramResponse(
        version=latest["version"],
        scope=latest["scope"],
        approved=latest["approved"],
        program=program,
    )


@router.get("/{trip_id}/preferences", response_model=TripPreferences | None)
def get_preferences(
    trip_id: int,
    service: TripService = Depends(get_trip_service),
) -> TripPreferences | None:
    details = service.get_trip_details(trip_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
    if details.preferences is None:
        return None
    return TripPreferences.model_validate(details.preferences)


@router.post("/{trip_id}/runs", response_model=CreateTripResponse)
def start_run(
    trip_id: int,
    body: StartRunRequest,
    service: TripService = Depends(get_trip_service),
    run_manager: RunManager = Depends(get_run_manager),
) -> CreateTripResponse:
    try:
        state = service.prepare_continue_trip(trip_id, body.scope)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    state["review_mode"] = "deferred"
    run_id = run_manager.start_run(state)
    return CreateTripResponse(trip_id=trip_id, run_id=run_id)


@router.post("/{trip_id}/review", response_model=ReviewResponse)
def submit_review(
    trip_id: int,
    body: ReviewRequest,
    service: TripService = Depends(get_trip_service),
    run_manager: RunManager = Depends(get_run_manager),
) -> ReviewResponse:
    run_id: str | None = None
    try:
        if body.action == "rebuild":
            state = service.prepare_rebuild_state(trip_id)
            run_id = run_manager.start_run(state)
        else:
            service.submit_review(trip_id, body.action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    details = service.get_trip_details(trip_id)
    status = details.trip["status"] if details else "unknown"
    if body.action == "rebuild":
        status = "building"

    return ReviewResponse(trip_id=trip_id, status=status, run_id=run_id)
