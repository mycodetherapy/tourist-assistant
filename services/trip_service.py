"""Оркестрация поездок: граф, БД — общий слой для API."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Literal

from langchain_core.messages import HumanMessage

from db.constants import BOOTSTRAP_USER_ID
from db import (
    TripSummary,
    create_trip,
    delete_item_feedback,
    delete_trip,
    get_itinerary_version,
    get_latest_itinerary,
    get_preferences,
    get_trip,
    get_user_profile,
    list_item_feedback,
    list_item_feedback_by_index,
    list_trips,
    log_agent_run,
    save_itinerary_version,
    save_preferences,
    save_user_profile,
    upsert_item_feedback,
)
from input_validation import sanitize_and_validate
from models.schemas import FinalProgram, normalize_stored_program
from models.state import AgentState
from observability import (
    build_langfuse_callbacks,
    flush_langfuse,
    invoke_config,
    langfuse_metadata,
)
from onboarding import TripPreferences, build_search_context, merge_trip_preferences, normalize_trip_preferences
from planning import human_message_for_scope
from program.item_key import make_item_key, make_route_stop_key
from program.parse_items import (
    VOTABLE_SECTIONS,
    ParsedProgram,
    parse_program_sections,
)
from search.context import set_session

ProgramSectionKey = Literal["routes", "route_stops", "lifehacks", "events", "dining"]
VotableSectionKey = Literal["routes", "route_stops", "lifehacks", "events", "dining"]
CityFactStatusName = Literal["pending", "ready", "failed", "skipped", "idle"]
ItemVote = Literal[1, -1]


def _resolve_item_vote(
    *,
    section: VotableSectionKey,
    index: int,
    text: str,
    votes_by_key: dict[str, int],
    votes_by_index: dict[tuple[str, int], int],
) -> ItemVote | None:
    """Только по item_key — индекс после пересборки нестабилен."""
    _ = (index, votes_by_index)
    item_key = make_item_key(section, text)
    raw = votes_by_key.get(item_key)
    return raw if raw in (1, -1) else None


@dataclass(frozen=True)
class ProgramItemView:
    index: int
    item_key: str
    text: str
    vote: ItemVote | None
    poi_id: str | None = None


@dataclass(frozen=True)
class ProgramSectionView:
    intro: str
    items: tuple[ProgramItemView, ...]


@dataclass(frozen=True)
class ProgramView:
    version: int
    version_id: int
    scope: str
    approved: bool
    program: FinalProgram
    sections: dict[ProgramSectionKey, ProgramSectionView]
    data_warnings: tuple[str, ...] = ()
    city_fact_status: CityFactStatusName = "idle"


@dataclass(frozen=True)
class GraphRunResult:
    """Результат одного прогона графа."""

    state: AgentState
    run_id: str
    version_id: int | None


@dataclass(frozen=True)
class TripDetails:
    """Детали поездки для API."""

    trip: dict[str, Any]
    preferences: dict[str, Any] | None
    latest_itinerary: dict[str, Any] | None


class TripService:
    """Сценарии работы с поездками без привязки к HTTP или терминалу."""

    def apply_preferences(self, prefs: TripPreferences) -> str:
        """Сохраняет предпочтения в search/context для tools и промптов."""
        normalized = normalize_trip_preferences(prefs)
        ctx = build_search_context(normalized)
        set_session(normalized, ctx)
        return ctx

    def create_new_trip(
        self,
        *,
        city: str,
        dates: str,
        origin_city: str,
        user_query: str,
        preferences: TripPreferences,
        user_id: int,
    ) -> int:
        """Создаёт поездку, сохраняет предпочтения и профиль пользователя."""
        city_v = sanitize_and_validate(city, "city")
        dates_v = sanitize_and_validate(dates, "dates")
        origin_v = sanitize_and_validate(origin_city, "city")
        query_v = sanitize_and_validate(user_query, "message")
        preferences = normalize_trip_preferences(preferences)
        prefs_dict = preferences.model_dump()
        self.apply_preferences(preferences)
        save_user_profile(prefs_dict, user_id=user_id)
        trip_id = create_trip(city_v, dates_v, origin_v, query_v, user_id=user_id)
        save_preferences(trip_id, prefs_dict)
        from services.saas_events import audit

        audit(
            action="trip.create",
            entity_type="trip",
            entity_id=str(trip_id),
            user_id=user_id,
            metadata={"city": city_v},
        )
        return trip_id

    def update_trip_preferences(
        self,
        trip_id: int,
        *,
        user_id: int,
        update: dict[str, Any],
    ) -> TripPreferences:
        """Обновляет предпочтения поездки (travel_party, route_anchor)."""
        details = self.get_trip_details(trip_id, user_id=user_id)
        if details is None:
            raise ValueError("Поездка не найдена")
        merged = merge_trip_preferences(details.preferences, update)
        save_preferences(trip_id, merged.model_dump())
        self.apply_preferences(merged)
        return merged

    def build_initial_state(
        self,
        *,
        trip_id: int,
        city: str,
        dates: str,
        origin_city: str,
        search_context: str,
        preferences_dict: dict[str, Any],
        rebuild_scope: str,
        user_message: str,
        base_program: dict[str, Any] | None = None,
        retry_count: int = 0,
    ) -> AgentState:
        """Собирает начальное состояние графа."""
        state: AgentState = {
            "trip_id": trip_id,
            "city": city,
            "dates": dates,
            "origin_city": origin_city,
            "search_context": search_context,
            "preferences": preferences_dict,
            "rebuild_scope": rebuild_scope,
            "retry_count": retry_count,
            "critic_passed": False,
            "critic_notes": "",
            "critic_retry_target": "researcher",
            "data_warnings": [],
            "messages": [HumanMessage(content=user_message)],
        }
        if base_program is not None:
            state["base_program"] = base_program
            if rebuild_scope in ("full", "routes", "events", "dining"):
                from program.route_feedback import snapshot_route_feedback

                snapshot = snapshot_route_feedback(
                    base_program, trip_id, rebuild_scope
                )
                if snapshot is not None:
                    state["route_feedback_snapshot"] = snapshot
        return state

    def prepare_continue_trip(
        self,
        trip_id: int,
        rebuild_scope: str,
    ) -> AgentState:
        """Готовит состояние для продолжения сохранённой поездки."""
        trip = get_trip(trip_id)
        if trip is None:
            raise ValueError(f"Поездка #{trip_id} не найдена")
        prefs_data = get_preferences(trip_id)
        if prefs_data:
            prefs = TripPreferences.model_validate(prefs_data)
            search_context = self.apply_preferences(prefs)
            preferences_dict = prefs.model_dump()
        else:
            search_context = ""
            preferences_dict = {}
        latest = get_latest_itinerary(trip_id)
        base_program = normalize_stored_program(latest["program"]) if latest else None
        from search.context import set_route_materials
        from search.route_materials_store import ensure_route_materials_for_trip

        cached = ensure_route_materials_for_trip(
            trip_id,
            city=trip["city"],
            dates=trip["dates"],
            base_program=base_program,
        )
        if cached is not None:
            set_route_materials(cached.model_dump())
        user_message = human_message_for_scope(rebuild_scope)
        return self.build_initial_state(
            trip_id=trip_id,
            city=trip["city"],
            dates=trip["dates"],
            origin_city=trip["origin_city"],
            search_context=search_context,
            preferences_dict=preferences_dict,
            rebuild_scope=rebuild_scope,
            user_message=user_message,
            base_program=base_program,
        )

    def run_graph(
        self,
        state: AgentState,
        *,
        on_progress: Callable[[str], None] | None = None,
        graph_run_id: str | None = None,
    ) -> GraphRunResult:
        """Запускает мультиагентный граф и сохраняет версию программы."""
        trip_id = int(state["trip_id"])
        rebuild_scope = str(state.get("rebuild_scope", "full"))

        if on_progress:
            on_progress(
                f"Запуск: {state['origin_city']} → {state['city']}, {state['dates']}"
            )

        run_state: AgentState = {
            **state,
            "retry_count": state.get("retry_count", 0),
            "critic_passed": False,
            "critic_notes": "",
            "critic_retry_target": "researcher",
            "data_warnings": list(state.get("data_warnings") or []),
        }
        config = invoke_config(trip_id, rebuild_scope=rebuild_scope)
        run_id = str(uuid.uuid4())
        callbacks = build_langfuse_callbacks(trace_id=run_id)
        if callbacks:
            config["callbacks"] = [*callbacks, *(config.get("callbacks") or [])]
            config.setdefault("metadata", {}).update(
                langfuse_metadata(
                    trip_id=trip_id,
                    rebuild_scope=rebuild_scope,
                    retry_count=int(state.get("retry_count", 0)),
                )
            )
            tags = config.get("metadata", {}).get("tags")
            if isinstance(tags, list):
                config["metadata"]["tags"] = ",".join(str(t) for t in tags)

        started = perf_counter()
        cb = None
        try:
            from langchain_community.callbacks.manager import (  # type: ignore
                get_openai_callback,
            )
        except Exception:
            get_openai_callback = None  # type: ignore

        from services.graph_metrics import stream_graph_with_metrics

        if get_openai_callback is not None:
            with get_openai_callback() as cb:
                result, run_metrics = stream_graph_with_metrics(run_state, config)
        else:
            result, run_metrics = stream_graph_with_metrics(run_state, config)

        flush_langfuse()

        duration_ms = int((perf_counter() - started) * 1000)
        prompt_tokens = int(getattr(cb, "prompt_tokens", 0)) if cb else None
        completion_tokens = int(getattr(cb, "completion_tokens", 0)) if cb else None
        total_tokens = int(getattr(cb, "total_tokens", 0)) if cb else None
        total_cost_usd = float(getattr(cb, "total_cost", 0.0)) if cb else None
        log_agent_run(
            trip_id,
            run_id=run_id,
            rebuild_scope=rebuild_scope,
            duration_ms=duration_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            total_cost_usd=total_cost_usd,
            node_timings=run_metrics.to_dict(),
        )

        version_id: int | None = None
        program = result.get("program")
        if program:
            program_to_save = dict(program)
            warnings = result.get("data_warnings") or program_to_save.get("data_warnings")
            if warnings:
                program_to_save["data_warnings"] = list(warnings)
            version_id = save_itinerary_version(
                trip_id,
                program_to_save,
                scope=rebuild_scope,
                approved=False,
            )

        trip = get_trip(trip_id)
        if trip is not None:
            from services.saas_events import usage_from_graph_run

            usage_from_graph_run(
                user_id=int(trip["user_id"]),
                trip_id=trip_id,
                scope=rebuild_scope,
                graph_run_id=graph_run_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=total_cost_usd,
            )

        return GraphRunResult(state=result, run_id=run_id, version_id=version_id)

    def delete_trip_by_id(
        self,
        trip_id: int,
        *,
        user_id: int,
        has_active_run: bool = False,
    ) -> None:
        """Удаляет поездку из БД. Запрещено во время активного фонового прогона."""
        if get_trip(trip_id, user_id=user_id) is None:
            raise ValueError(f"Поездка #{trip_id} не найдена")
        if has_active_run:
            raise ValueError("Нельзя удалить поездку во время сборки программы")
        if not delete_trip(trip_id, user_id=user_id):
            raise ValueError(f"Поездка #{trip_id} не найдена")

    def get_trip_details(self, trip_id: int, *, user_id: int) -> TripDetails | None:
        """Метаданные, предпочтения и последняя программа."""
        trip = get_trip(trip_id, user_id=user_id)
        if trip is None:
            return None
        return TripDetails(
            trip=trip,
            preferences=get_preferences(trip_id),
            latest_itinerary=get_latest_itinerary(trip_id),
        )

    def list_all_trips(self, user_id: int, limit: int = 20) -> list[TripSummary]:
        return list_trips(limit=limit, user_id=user_id)

    def get_profile(self, user_id: int) -> dict[str, Any] | None:
        return get_user_profile(user_id)

    def parse_program(self, data: dict[str, Any]) -> FinalProgram:
        return FinalProgram.model_validate(normalize_stored_program(data))

    def _attach_feedback(
        self,
        parsed: ParsedProgram,
        *,
        trip_id: int,
        program_data: dict[str, Any],
    ) -> dict[ProgramSectionKey, ProgramSectionView]:
        votes_by_key = list_item_feedback(trip_id)
        votes_by_index = list_item_feedback_by_index(trip_id)
        sections: dict[ProgramSectionKey, ProgramSectionView] = {}
        for key in VOTABLE_SECTIONS:
            if key == "route_stops":
                from program.route_stops import collect_route_stop_poi_ids

                poi_labels = collect_route_stop_poi_ids(program_data)
                items = tuple(
                    ProgramItemView(
                        index=index,
                        item_key=make_route_stop_key(poi_id),
                        text=f"{label} [{poi_id}]",
                        vote=(
                            int(v)
                            if (v := votes_by_key.get(make_route_stop_key(poi_id)))
                            in (1, -1)
                            else None
                        ),
                        poi_id=poi_id,
                    )
                    for index, (poi_id, label) in enumerate(poi_labels.items())
                )
                sections[key] = ProgramSectionView(intro="", items=items)
                continue
            section = getattr(parsed, key)
            items = tuple(
                ProgramItemView(
                    index=index,
                    item_key=make_item_key(key, text),
                    text=text,
                    vote=_resolve_item_vote(
                        section=key,
                        index=index,
                        text=text,
                        votes_by_key=votes_by_key,
                        votes_by_index=votes_by_index,
                    ),
                )
                for index, text in enumerate(section.items)
            )
            sections[key] = ProgramSectionView(intro=section.intro, items=items)
        return sections

    def build_program_view(
        self,
        trip_id: int,
        program_data: dict[str, Any],
        *,
        version: int = 0,
        version_id: int = 0,
        scope: str = "full",
        approved: bool = False,
    ) -> ProgramView:
        """Программа из dict (например state графа) с оценками из БД."""
        raw_warnings = program_data.get("data_warnings") or []
        data_warnings = tuple(
            str(item).strip() for item in raw_warnings if str(item).strip()
        )
        program = self.parse_program(program_data)
        parsed = parse_program_sections(program.model_dump())
        sections = self._attach_feedback(
            parsed, trip_id=trip_id, program_data=program_data
        )
        city_fact_status = self._resolve_city_fact_status(program_data)
        return ProgramView(
            version=version,
            version_id=version_id,
            scope=scope,
            approved=approved,
            program=program,
            sections=sections,
            data_warnings=data_warnings,
            city_fact_status=city_fact_status,
        )

    @staticmethod
    def _resolve_city_fact_status(program_data: dict[str, Any]) -> CityFactStatusName:
        raw = program_data.get("city_fact_status")
        if raw in ("pending", "ready", "failed", "skipped"):
            return raw  # type: ignore[return-value]
        if str(program_data.get("lifehacks") or "").strip():
            return "ready"
        return "idle"

    def get_program_view(
        self,
        trip_id: int,
        *,
        user_id: int = BOOTSTRAP_USER_ID,
    ) -> ProgramView | None:
        """Программа с разбивкой на пункты и сохранёнными оценками."""
        details = self.get_trip_details(trip_id, user_id=user_id)
        if details is None or details.latest_itinerary is None:
            return None
        latest = details.latest_itinerary
        trip = details.trip
        prefs = details.preferences or {}
        program_data = dict(latest["program"])
        from agents.finalize_helpers import repair_program_routes

        program_data = repair_program_routes(
            program_data,
            trip_id=trip_id,
            city=str(trip["city"]),
            dates=str(trip["dates"]),
            transport=str(prefs.get("transport_preference") or "mixed"),
            pace=str(prefs.get("pace") or "moderate"),
        )
        return self.build_program_view(
            trip_id,
            program_data,
            version=int(latest["version"]),
            version_id=int(latest["id"]),
            scope=latest["scope"],
            approved=latest["approved"],
        )

    def set_item_feedback(
        self,
        trip_id: int,
        *,
        section: VotableSectionKey,
        vote: ItemVote | None,
        item_key: str | None = None,
        item_index: int | None = None,
        version_id: int | None = None,
        program_data: dict[str, Any] | None = None,
    ) -> None:
        """Сохраняет, обновляет или снимает оценку пункта подборки."""
        if section not in VOTABLE_SECTIONS:
            raise ValueError(f"Неизвестный раздел: {section}")
        if get_trip(trip_id) is None:
            raise ValueError("Поездка не найдена")

        latest = get_latest_itinerary(trip_id)
        if program_data is not None:
            program = self.parse_program(program_data)
        elif latest is not None:
            program = self.parse_program(latest["program"])
        else:
            raise ValueError("Программа не найдена")
        if version_id is not None and get_itinerary_version(trip_id, version_id) is None:
            raise ValueError("Версия программы не найдена")
        parsed = parse_program_sections(program.model_dump())
        section_data = getattr(parsed, section)
        resolved_key: str | None = None
        matched_index: int | None = None

        if section == "route_stops":
            from program.item_key import parse_route_stop_key
            from program.route_stops import collect_route_stop_poi_ids

            valid_pois = collect_route_stop_poi_ids(program.model_dump())
            poi_ids = list(valid_pois.keys())
            normalized_key = (item_key or "").strip()
            poi_id: str | None = None
            if normalized_key.startswith("poi:"):
                poi_id = parse_route_stop_key(normalized_key)
            elif item_index is not None and 0 <= item_index < len(poi_ids):
                poi_id = poi_ids[item_index]
            if poi_id and poi_id in valid_pois:
                matched_index = poi_ids.index(poi_id)
                resolved_key = make_route_stop_key(poi_id)
        else:
            normalized_key = (item_key or "").strip()
            if normalized_key:
                for index, text in enumerate(section_data.items):
                    if make_item_key(section, text) == normalized_key:
                        matched_index = index
                        resolved_key = normalized_key
                        break
            elif item_index is not None:
                if 0 <= item_index < len(section_data.items):
                    matched_index = item_index
                    resolved_key = make_item_key(section, section_data.items[item_index])

        if matched_index is None or resolved_key is None:
            raise ValueError("Пункт подборки не найден")

        if vote == 1 and section == "routes":
            from program.route_feedback import MAX_LIKED_ROUTES_PER_TRIP, count_liked_routes

            existing_votes = list_item_feedback(trip_id)
            already_liked = existing_votes.get(resolved_key) == 1
            if not already_liked:
                liked_count = count_liked_routes(program.model_dump(), trip_id)
                if liked_count >= MAX_LIKED_ROUTES_PER_TRIP:
                    raise ValueError(
                        f"Лимит лайков маршрутов ({MAX_LIKED_ROUTES_PER_TRIP}) для поездки"
                    )

        if vote == 1 and section == "route_stops":
            from program.route_feedback import (
                MAX_LIKED_ROUTE_STOPS_PER_TRIP,
                count_liked_route_stops,
            )

            existing_votes = list_item_feedback(trip_id)
            already_liked = existing_votes.get(resolved_key) == 1
            if not already_liked:
                liked_count = count_liked_route_stops(trip_id)
                if liked_count >= MAX_LIKED_ROUTE_STOPS_PER_TRIP:
                    raise ValueError(
                        f"Лимит лайков остановок ({MAX_LIKED_ROUTE_STOPS_PER_TRIP})"
                    )

        if vote is None:
            from db.repository import delete_feedback_at_index

            delete_item_feedback(trip_id, section, resolved_key)
            delete_feedback_at_index(trip_id, section, matched_index)
            return
        from db.repository import delete_feedback_at_index

        delete_feedback_at_index(
            trip_id,
            section,
            matched_index,
            except_item_key=resolved_key,
        )
        storage_version_id = int(latest["id"]) if latest is not None else None
        upsert_item_feedback(
            trip_id,
            storage_version_id,
            section,
            matched_index,
            resolved_key,
            vote,
        )
