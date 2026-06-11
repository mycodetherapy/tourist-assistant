"""Маршруты поездок."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

from api.deps import get_run_manager, get_trip_service
from api.schemas.requests import (
    AffiliateClickRequest,
    CreateTripRequest,
    ItemFeedbackRequest,
    ReviewRequest,
    StartRunRequest,
)
from api.schemas.responses import (
    CreateTripResponse,
    ProgramItemResponse,
    ProgramResponse,
    ProgramSectionResponse,
    ReviewResponse,
    StructuredProgramResponse,
    TripDetailResponse,
    TripSummaryResponse,
)
from services.trip_service import ProgramView
from onboarding.preferences import TripPreferences, normalize_trip_preferences
from services.run_manager import RunManager
from services.trip_service import TripService

router = APIRouter(prefix="/trips", tags=["trips"])


def _map_section(view: ProgramView, key: str) -> ProgramSectionResponse:
    section = view.sections.get(key)  # type: ignore[arg-type]
    if section is None:
        return ProgramSectionResponse(intro="", items=[])
    return ProgramSectionResponse(
        intro=section.intro,
        items=[
            ProgramItemResponse(
                index=i.index,
                item_key=i.item_key,
                text=i.text,
                vote=i.vote,
                poi_id=i.poi_id,
            )
            for i in section.items
        ],
    )


def _program_response(view: ProgramView) -> ProgramResponse:
    from search.ticket_links import normalize_tickets_markdown

    tickets_md = normalize_tickets_markdown(view.program.tickets)
    program = view.program.model_copy(update={"tickets": tickets_md})
    sections = StructuredProgramResponse(
        tickets=_map_section(view, "tickets"),
        routes=_map_section(view, "routes"),
        route_stops=_map_section(view, "route_stops"),
        lifehacks=_map_section(view, "lifehacks"),
        events=_map_section(view, "events"),
        dining=_map_section(view, "dining"),
    )
    return ProgramResponse(
        version=view.version,
        version_id=view.version_id,
        scope=view.scope,
        approved=view.approved,
        program=program,
        sections=sections,
    )


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
    preferences = normalize_trip_preferences(body.preferences)
    trip_id = service.create_new_trip(
        city=body.city,
        dates=body.dates,
        origin_city=body.origin_city,
        user_query=body.user_query,
        preferences=preferences,
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
            search_context=service.apply_preferences(preferences),
            preferences_dict=preferences.model_dump(),
            rebuild_scope="full",
            user_message=trip.get("user_query") or body.user_query,
            review_mode="deferred",
        )
        run_id = run_manager.start_run(state)
    return CreateTripResponse(trip_id=trip_id, run_id=run_id)


@router.delete("/{trip_id}", status_code=204, response_class=Response)
def delete_trip(
    trip_id: int,
    service: TripService = Depends(get_trip_service),
    run_manager: RunManager = Depends(get_run_manager),
) -> Response:
    try:
        service.delete_trip_by_id(
            trip_id,
            has_active_run=run_manager.has_active_run_for_trip(trip_id),
        )
    except ValueError as exc:
        message = str(exc)
        if "сборки" in message:
            raise HTTPException(status_code=409, detail=message) from exc
        raise HTTPException(status_code=404, detail=message) from exc
    run_manager.forget_runs_for_trip(trip_id)
    return Response(status_code=204)


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
    view = service.get_program_view(trip_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Программа не найдена")
    return _program_response(view)


@router.put("/{trip_id}/program/feedback", response_model=ProgramResponse)
def set_program_feedback(
    trip_id: int,
    body: ItemFeedbackRequest,
    service: TripService = Depends(get_trip_service),
) -> ProgramResponse:
    try:
        service.set_item_feedback(
            trip_id,
            version_id=body.version_id,
            section=body.section,
            item_key=body.item_key,
            item_index=body.item_index,
            vote=body.vote,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    view = service.get_program_view(trip_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Программа не найдена")
    return _program_response(view)


@router.post("/{trip_id}/affiliate-clicks", status_code=204, response_class=Response)
def log_affiliate_click(
    trip_id: int,
    body: AffiliateClickRequest,
    service: TripService = Depends(get_trip_service),
) -> Response:
    """Локальный учёт клика по affiliate-ссылке в блоке билетов."""
    if service.get_trip_details(trip_id) is None:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
    from db.affiliate_repository import log_affiliate_click as persist_click
    from search.affiliate.programs import detect_provider
    from search.affiliate.sub_id import build_sub_id

    provider = detect_provider(body.target_url)
    sub_id = (
        build_sub_id(trip_id, "tickets", provider)
        if provider is not None
        else None
    )
    persist_click(
        trip_id,
        target_url=body.target_url,
        provider=provider.key if provider else body.provider,
        sub_id=sub_id,
    )
    return Response(status_code=204)


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
