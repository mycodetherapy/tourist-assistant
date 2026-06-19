"""Маршруты поездок."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

from api.auth.service import AuthError, require_user_llm_config
from api.deps import get_current_user, get_run_manager, get_trip_service
from api.schemas.requests import (
    CreateTripRequest,
    GeocodeRequest,
    ItemFeedbackRequest,
    ReverseGeocodeRequest,
    StartRunRequest,
    UpdatePreferencesRequest,
)
from api.schemas.responses import (
    CityCenterResponse,
    CreateTripResponse,
    GeocodeResponse,
    GeocodeResultResponse,
    ProgramItemResponse,
    ProgramResponse,
    ProgramSectionResponse,
    ReverseGeocodeResponse,
    StructuredProgramResponse,
    TripDetailResponse,
    TripSummaryResponse,
)
from db.users import User
from onboarding.preferences import TripPreferences, merge_trip_preferences, normalize_trip_preferences
from services.run_manager import RunManager
from services.trip_service import ProgramView, TripService

router = APIRouter(prefix="/trips", tags=["trips"])


def _geocode_response(query: str, city_hint: str) -> GeocodeResponse:
    from search.yandex.client import geocode_places as yandex_geocode

    features = yandex_geocode(query, city_hint=city_hint, results=5)
    results: list[GeocodeResultResponse] = []
    for feature in features:
        coords = feature.get("geometry", {}).get("coordinates") or []
        if len(coords) < 2:
            continue
        lon, lat = float(coords[0]), float(coords[1])
        props = feature.get("properties") or {}
        meta = props.get("CompanyMetaData") or {}
        label = str(meta.get("address") or props.get("name") or query).strip()
        results.append(GeocodeResultResponse(lat=lat, lon=lon, label=label))
    if not results and city_hint:
        from search.osm.nominatim import resolve_city_center

        center = resolve_city_center(f"{query}, {city_hint}")
        if center is not None:
            results.append(
                GeocodeResultResponse(
                    lat=center.lat,
                    lon=center.lon,
                    label=center.display_name or query,
                )
            )
    return GeocodeResponse(results=results)


def _reverse_geocode_response(lat: float, lon: float, city_hint: str = "") -> ReverseGeocodeResponse:
    from search.osm.nominatim import reverse_geocode_label as nominatim_reverse
    from search.yandex.client import reverse_geocode_label as yandex_reverse

    label = yandex_reverse(lat, lon, city_hint=city_hint)
    if not label:
        label = nominatim_reverse(lat, lon)
    if not label:
        label = f"{lat:.5f}, {lon:.5f}"
    return ReverseGeocodeResponse(lat=lat, lon=lon, label=label)


def _llm_key_http_error(exc: AuthError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": "llm_key_required", "message": str(exc)},
    )


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
    program = view.program
    sections = StructuredProgramResponse(
        routes=_map_section(view, "routes"),
        route_stops=_map_section(view, "route_stops"),
        lifehacks=_map_section(view, "lifehacks"),
    )
    return ProgramResponse(
        version=view.version,
        version_id=view.version_id,
        scope=view.scope,
        approved=view.approved,
        program=program,
        sections=sections,
        data_warnings=list(view.data_warnings),
        city_fact_status=view.city_fact_status,
    )


@router.get("", response_model=list[TripSummaryResponse])
def list_trips(
    user: User = Depends(get_current_user),
    service: TripService = Depends(get_trip_service),
) -> list[TripSummaryResponse]:
    return [
        TripSummaryResponse(
            id=t.id,
            city=t.city,
            updated_at=t.updated_at,
        )
        for t in service.list_all_trips(user.id)
    ]


@router.post("/geocode", response_model=GeocodeResponse)
def geocode_query(
    body: GeocodeRequest,
    user: User = Depends(get_current_user),
) -> GeocodeResponse:
    """Геокодинг адреса (мастер новой поездки, city_hint обязателен)."""
    _ = user
    return _geocode_response(body.query.strip(), body.city_hint.strip())


@router.post("/reverse-geocode", response_model=ReverseGeocodeResponse)
def reverse_geocode_query(
    body: ReverseGeocodeRequest,
    user: User = Depends(get_current_user),
) -> ReverseGeocodeResponse:
    """Обратный геокодинг для мастера новой поездки."""
    _ = user
    return _reverse_geocode_response(body.lat, body.lon, body.city_hint.strip())


@router.post("", response_model=CreateTripResponse, status_code=201)
def create_trip(
    body: CreateTripRequest,
    user: User = Depends(get_current_user),
    service: TripService = Depends(get_trip_service),
    run_manager: RunManager = Depends(get_run_manager),
) -> CreateTripResponse:
    raw_preferences = (body.preferences.model_dump() if body.preferences else {}) | {
        "route_anchor": body.route_anchor.model_dump() if body.route_anchor else None
    }
    preferences = normalize_trip_preferences(raw_preferences)
    llm_config = None
    if body.start_run:
        try:
            llm_config = require_user_llm_config(user.id)
        except AuthError as exc:
            raise _llm_key_http_error(exc) from exc
    trip_id = service.create_new_trip(
        city=body.city,
        dates="Без дат",
        origin_city=body.city,
        user_query=body.user_query,
        preferences=preferences,
        user_id=user.id,
    )
    run_id: str | None = None
    if body.start_run:
        assert llm_config is not None
        details = service.get_trip_details(trip_id, user_id=user.id)
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
        )
        run_id = run_manager.start_run(state, llm_config=llm_config)
    return CreateTripResponse(trip_id=trip_id, run_id=run_id)


@router.delete("/{trip_id}", status_code=204, response_class=Response)
def delete_trip(
    trip_id: int,
    user: User = Depends(get_current_user),
    service: TripService = Depends(get_trip_service),
    run_manager: RunManager = Depends(get_run_manager),
) -> Response:
    try:
        service.delete_trip_by_id(
            trip_id,
            user_id=user.id,
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
    user: User = Depends(get_current_user),
    service: TripService = Depends(get_trip_service),
) -> TripDetailResponse:
    details = service.get_trip_details(trip_id, user_id=user.id)
    if details is None:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
    trip = details.trip
    return TripDetailResponse(
        id=int(trip["id"]),
        city=trip["city"],
        user_query=trip.get("user_query"),
        created_at=trip["created_at"],
        updated_at=trip["updated_at"],
    )


@router.get("/{trip_id}/program", response_model=ProgramResponse)
def get_program(
    trip_id: int,
    user: User = Depends(get_current_user),
    service: TripService = Depends(get_trip_service),
) -> ProgramResponse:
    if service.get_trip_details(trip_id, user_id=user.id) is None:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
    view = service.get_program_view(trip_id, user_id=user.id)
    if view is None:
        raise HTTPException(status_code=404, detail="Программа не найдена")
    return _program_response(view)


@router.put("/{trip_id}/preferences", response_model=TripPreferences)
def update_preferences(
    trip_id: int,
    body: UpdatePreferencesRequest,
    user: User = Depends(get_current_user),
    service: TripService = Depends(get_trip_service),
) -> TripPreferences:
    if service.get_trip_details(trip_id, user_id=user.id) is None:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
    update = body.model_dump(exclude_unset=True)
    if not update:
        raise HTTPException(status_code=400, detail="Нет полей для обновления")
    try:
        return service.update_trip_preferences(trip_id, user_id=user.id, update=update)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{trip_id}/city-center", response_model=CityCenterResponse)
def get_city_center(
    trip_id: int,
    user: User = Depends(get_current_user),
    service: TripService = Depends(get_trip_service),
) -> CityCenterResponse:
    details = service.get_trip_details(trip_id, user_id=user.id)
    if details is None:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
    from search.osm.nominatim import resolve_city_center

    city = str(details.trip["city"])
    center = resolve_city_center(city)
    if center is None:
        raise HTTPException(status_code=404, detail=f"Не удалось определить центр города: {city}")
    return CityCenterResponse(
        lat=center.lat,
        lon=center.lon,
        label=center.display_name or city,
    )


@router.post("/{trip_id}/geocode", response_model=GeocodeResponse)
def geocode_address(
    trip_id: int,
    body: GeocodeRequest,
    user: User = Depends(get_current_user),
    service: TripService = Depends(get_trip_service),
) -> GeocodeResponse:
    details = service.get_trip_details(trip_id, user_id=user.id)
    if details is None:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
    city_hint = (body.city_hint or str(details.trip["city"])).strip()
    return _geocode_response(body.query.strip(), city_hint)


@router.post("/{trip_id}/reverse-geocode", response_model=ReverseGeocodeResponse)
def reverse_geocode_address(
    trip_id: int,
    body: ReverseGeocodeRequest,
    user: User = Depends(get_current_user),
    service: TripService = Depends(get_trip_service),
) -> ReverseGeocodeResponse:
    details = service.get_trip_details(trip_id, user_id=user.id)
    if details is None:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
    city_hint = (body.city_hint or str(details.trip["city"])).strip()
    return _reverse_geocode_response(body.lat, body.lon, city_hint)


@router.put("/{trip_id}/program/feedback", response_model=ProgramResponse)
def set_program_feedback(
    trip_id: int,
    body: ItemFeedbackRequest,
    user: User = Depends(get_current_user),
    service: TripService = Depends(get_trip_service),
) -> ProgramResponse:
    if service.get_trip_details(trip_id, user_id=user.id) is None:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
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
    view = service.get_program_view(trip_id, user_id=user.id)
    if view is None:
        raise HTTPException(status_code=404, detail="Программа не найдена")
    return _program_response(view)


@router.get("/{trip_id}/preferences", response_model=TripPreferences | None)
def get_preferences(
    trip_id: int,
    user: User = Depends(get_current_user),
    service: TripService = Depends(get_trip_service),
) -> TripPreferences | None:
    details = service.get_trip_details(trip_id, user_id=user.id)
    if details is None:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
    if details.preferences is None:
        return None
    return TripPreferences.model_validate(details.preferences)


@router.post("/{trip_id}/runs", response_model=CreateTripResponse)
def start_run(
    trip_id: int,
    body: StartRunRequest,
    user: User = Depends(get_current_user),
    service: TripService = Depends(get_trip_service),
    run_manager: RunManager = Depends(get_run_manager),
) -> CreateTripResponse:
    if service.get_trip_details(trip_id, user_id=user.id) is None:
        raise HTTPException(status_code=404, detail="Поездка не найдена")
    try:
        llm_config = require_user_llm_config(user.id)
        state = service.prepare_continue_trip(trip_id, body.scope)
    except AuthError as exc:
        raise _llm_key_http_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    run_id = run_manager.start_run(state, llm_config=llm_config)
    return CreateTripResponse(trip_id=trip_id, run_id=run_id)
