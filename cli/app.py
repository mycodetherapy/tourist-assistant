"""CLI: меню (новая / продолжить), опросник, SQLite, invoke графа."""

from __future__ import annotations

import json
import os
import uuid
from time import perf_counter
from typing import Any

from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from agents.graph import app
from agents.print_program import print_final_program
from config.settings import ensure_env
from db import (
    PlannedTripSummary,
    create_trip,
    ensure_user_profile_from_trips,
    get_latest_itinerary,
    get_preferences,
    get_trip,
    get_user_profile,
    init_db,
    list_planned_trips,
    list_trips,
    log_agent_run,
    save_itinerary_version,
    save_preferences,
    save_user_profile,
    update_trip_status,
)
from input_validation import sanitize_and_validate
from models.schemas import FinalProgram, normalize_stored_program
from models.state import AgentState
from observability import (
    build_langfuse_callbacks,
    flush_langfuse,
    invoke_config,
    langfuse_enabled,
    langfuse_metadata,
    langsmith_enabled,
)
from onboarding import (
    TripPreferences,
    build_search_context,
    resolve_preferences_for_new_trip,
)
from planning import REBUILD_SCOPES, human_message_for_scope, required_tools_for_scope
from search.context import set_session


def _format_runtime_error(exc: Exception) -> str:
    """Человекочитаемое сообщение для типичных сбоев LLM API."""
    text = str(exc)
    if "length" in text.lower() or "LengthFinishReason" in type(exc).__name__:
        return (
            "Ответ LLM обрезан по лимиту токенов (слишком большой контекст или программа).\n"
            "Повторите пересбор по разделам (билеты / мероприятия / питание) или сократите запрос.\n"
            f"Детали: {text}"
        )
    if any(
        marker in text
        for marker in ("401", "Invalid API Key", "AuthenticationError", "authentication")
    ):
        return (
            "Ошибка аутентификации LLM (401): провайдер не принял LLM_API_KEY.\n"
            "Проверьте .env: ключ с https://openrouter.ai/keys (не sk-or-... из .env.example).\n"
            f"Детали: {text}"
        )
    if "403" in text or "unsupported_country_region_territory" in text:
        return (
            "Ошибка LLM (403): провайдер OpenAI недоступен из вашего региона.\n"
            "По умолчанию запросы идут через Azure (LLM_OPENROUTER_PROVIDERS).\n"
            "Если ошибка остаётся — VPN или другая модель в LLM_MODEL.\n"
            f"Детали: {text}"
        )
    if "All providers have been ignored" in text:
        return (
            "Ошибка LLM (404): OpenRouter не нашёл провайдера для модели.\n"
            "Расширьте LLM_OPENROUTER_PROVIDERS или проверьте ignore в "
            "https://openrouter.ai/settings/privacy .\n"
            f"Детали: {text}"
        )
    if "No endpoints found that support tool use" in text:
        return (
            "Ошибка LLM (404): у выбранных провайдеров нет поддержки tool calling.\n"
            "Для openai/gpt-4o-mini tools доступны только через OpenAI (VPN из РФ).\n"
            "Рекомендуется: LLM_MODEL=openai/gpt-4.1-mini, LLM_OPENROUTER_PROVIDERS=Azure\n"
            f"Детали: {text}"
        )
    if "messages with role 'tool'" in text or "tool_calls" in text:
        return (
            "Ошибка LLM (400): некорректная история сообщений для API.\n"
            "Перезапустите python3 main.py. Если повторяется — сообщите об ошибке.\n"
            f"Детали: {text}"
        )
    return f"Ошибка выполнения: {text}"


def _prompt_line(label: str, default: str = "") -> str:
    """Запрашивает строку в терминале; Enter — значение по умолчанию."""
    if default:
        raw = input(f"{label} [{default}]: ").strip()
        return raw if raw else default
    return input(f"{label}: ").strip()


def _run_graph(state: AgentState) -> AgentState:
    """Запускает мультиагентный граф и возвращает финальное состояние."""
    trip_id = int(state["trip_id"])
    print(f"\nЗапуск: {state['origin_city']} → {state['city']}, {state['dates']}")
    if langsmith_enabled():
        print("Трейсинг: LangSmith включён (LANGCHAIN_TRACING_V2)")
    if langfuse_enabled():
        print("Трейсинг: LangFuse включён (LANGFUSE_ENABLED)")
    print(
        "Агенты: researcher → executor → writer → critic → human_review "
        "(1–2 минуты)...\n"
    )
    run_state: AgentState = {
        **state,
        "retry_count": state.get("retry_count", 0),
        "approved": False,
        "critic_passed": False,
        "critic_notes": "",
    }
    config = invoke_config(
        trip_id,
        rebuild_scope=state.get("rebuild_scope", "full"),
    )
    run_id = str(uuid.uuid4())
    callbacks = build_langfuse_callbacks(trace_id=run_id)
    if langfuse_enabled() and not callbacks:
        print(
            "Трейсинг: LangFuse включён, но callbacks не инициализировались "
            "(проверьте, что установлен пакет `langfuse` и заданы ключи)."
        )
    if callbacks:
        config["callbacks"] = [*callbacks, *(config.get("callbacks") or [])]
        config.setdefault("metadata", {}).update(
            langfuse_metadata(
                trip_id=trip_id,
                rebuild_scope=state.get("rebuild_scope", "full"),
                retry_count=int(state.get("retry_count", 0)),
            )
        )
        # LangFuse integration ругается на `metadata.tags` как list → приводим к строке.
        tags = config.get("metadata", {}).get("tags")
        if isinstance(tags, list):
            config["metadata"]["tags"] = ",".join(str(t) for t in tags)
    scope = str(state.get("rebuild_scope", "full"))
    started = perf_counter()

    # Метрики tokens/cost: работает для OpenAI-compatible LLM вызовов LangChain.
    # Для RU/нестандартных провайдеров callback может вернуть 0 — это ок.
    cb = None
    try:
        from langchain_community.callbacks.manager import (  # type: ignore
            get_openai_callback,
        )
    except Exception:
        get_openai_callback = None  # type: ignore

    if get_openai_callback is not None:
        with get_openai_callback() as cb:
            result = app.invoke(run_state, config=config)
    else:
        result = app.invoke(run_state, config=config)

    flush_langfuse()

    duration_ms = int((perf_counter() - started) * 1000)
    prompt_tokens = int(getattr(cb, "prompt_tokens", 0)) if cb else None
    completion_tokens = int(getattr(cb, "completion_tokens", 0)) if cb else None
    total_tokens = int(getattr(cb, "total_tokens", 0)) if cb else None
    total_cost_usd = float(getattr(cb, "total_cost", 0.0)) if cb else None

    log_agent_run(
        trip_id,
        run_id=run_id,
        rebuild_scope=scope,
        duration_ms=duration_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        total_cost_usd=total_cost_usd,
    )

    return result


def _apply_preferences_to_session(prefs: TripPreferences) -> str:
    """Сохраняет предпочтения в search/context для tools и промптов."""
    ctx = build_search_context(prefs)
    set_session(prefs, ctx)
    return ctx


def _collect_new_trip_inputs() -> tuple[str, str, str, str]:
    city_raw = _prompt_line("Город поездки")
    dates_raw = _prompt_line("Даты (например, 15-18 июля 2026)")
    origin_raw = _prompt_line("Город вылета", default="Москва")
    user_message_raw = _prompt_line(
        "Ваш запрос",
        default="Составь культурную программу поездки",
    )
    city = sanitize_and_validate(city_raw, "city")
    dates = sanitize_and_validate(dates_raw, "dates")
    origin_city = sanitize_and_validate(origin_raw, "city")
    user_message = sanitize_and_validate(user_message_raw, "message")
    return city, dates, origin_city, user_message


def _choose_rebuild_scope(*, has_program: bool) -> str:
    """Выбор полной или частичной пересборки программы."""
    if not has_program:
        print("\nСохранённой программы нет — будет полная сборка.")
        return "full"
    return _prompt_choice("Что пересобрать?", REBUILD_SCOPES, "full")


def _choose_trip_from_list() -> int | None:
    trips = list_trips()
    if not trips:
        print("Сохранённых поездок нет. Создайте новую.")
        return None
    print("\n--- Сохранённые поездки ---")
    for trip in trips:
        print(
            f"  [{trip.id}] {trip.city}, {trip.dates} "
            f"({trip.origin_city}) — {trip.status}"
        )
    raw = _prompt_line("ID поездки для продолжения")
    try:
        return int(raw)
    except ValueError:
        print("Некорректный ID.")
        return None


def _choose_planned_trip_from_list(
    trips: list[PlannedTripSummary],
    *,
    prompt: str = "Номер поездки",
) -> int | None:
    """Выбор поездки с программой по номеру в списке."""
    print("\n--- Поездки с сохранённой программой ---")
    for index, trip in enumerate(trips, start=1):
        print(
            f"  {index}. [{trip.id}] {trip.city}, {trip.dates} "
            f"({trip.origin_city}) — {trip.status}, "
            f"программа v{trip.last_version} ({trip.last_scope})"
        )
    raw = _prompt_line(prompt)
    try:
        choice = int(raw)
    except ValueError:
        print("Некорректный номер.")
        return None
    if 1 <= choice <= len(trips):
        return trips[choice - 1].id
    print("Номер вне списка.")
    return None


def _resolve_details_trip_id() -> int | None:
    """Выбор поездки для просмотра — всегда из списка с программой."""
    planned = list_planned_trips()
    if not planned:
        print("\nНет поездок с сохранённой программой.")
        return None
    return _choose_planned_trip_from_list(
        planned,
        prompt="Номер поездки для просмотра",
    )


def _print_trip_details(trip_id: int) -> None:
    """Печатает метаданные, предпочтения и последнюю программу из БД."""
    trip = get_trip(trip_id)
    if trip is None:
        print(f"Поездка #{trip_id} не найдена.")
        return

    print("\n" + "=" * 60)
    print(f"ПОЕЗДКА #{trip_id}")
    print("=" * 60)
    print(f"Маршрут: {trip['origin_city']} → {trip['city']}")
    print(f"Даты: {trip['dates']}")
    print(f"Статус: {trip['status']}")
    if trip.get("user_query"):
        print(f"Запрос: {trip['user_query']}")

    prefs_data = get_preferences(trip_id)
    if prefs_data:
        print("\n--- Предпочтения (опросник) ---")
        try:
            prefs = TripPreferences.model_validate(prefs_data)
            print(build_search_context(prefs))
        except ValidationError:
            print(json.dumps(prefs_data, ensure_ascii=False, indent=2))
    else:
        print("\n--- Предпочтения ---\nне сохранялись")

    latest = get_latest_itinerary(trip_id)
    if latest is None:
        print("\n--- Программа ---\nещё не сформирована")
        print("=" * 60)
        return

    print(
        f"\n--- Программа (версия {latest['version']}, "
        f"scope={latest['scope']}) ---"
    )
    program = FinalProgram.model_validate(normalize_stored_program(latest["program"]))
    print_final_program(program)


def _prompt_choice(label: str, options: list[tuple[str, str]], default_key: str) -> str:
    """Выбор пункта меню; Enter — значение по умолчанию."""
    print(f"\n{label}")
    default_index = next(
        (i for i, (key, _) in enumerate(options, start=1) if key == default_key),
        1,
    )
    for index, (_, text) in enumerate(options, start=1):
        mark = " (по умолчанию)" if index == default_index else ""
        print(f"  {index}. {text}{mark}")
    raw = input(f"Номер [Enter = {default_index}]: ").strip()
    if not raw:
        return default_key
    try:
        choice = int(raw)
    except ValueError:
        return default_key
    if 1 <= choice <= len(options):
        return options[choice - 1][0]
    return default_key


def main() -> None:
    ensure_env()

    init_db()
    ensure_user_profile_from_trips()
    search_backend = "Tavily" if os.getenv("TAVILY_API_KEY", "").strip() else "ddgs (ru-ru)"
    print("=" * 60)
    print("Туристический ассистент")
    print(f"Поиск данных: {search_backend}")
    print(f"База поездок: {os.getenv('DATABASE_PATH', 'data/trips.db')}")
    print("=" * 60)

    mode = _prompt_choice(
        "Режим",
        [
            ("new", "Новая поездка"),
            ("continue", "Продолжить сохранённую поездку"),
            ("details", "Показать подробности поездки"),
        ],
        "new",
    )

    if mode == "details":
        details_trip_id = _resolve_details_trip_id()
        if details_trip_id is not None:
            _print_trip_details(details_trip_id)
        raise SystemExit(0)

    trip_id: int
    city: str
    dates: str
    origin_city: str
    user_message: str
    search_context: str
    preferences_dict: dict[str, Any]
    rebuild_scope: str = "full"
    base_program: dict[str, Any] | None = None

    try:
        if mode == "continue":
            chosen = _choose_trip_from_list()
            if chosen is None:
                raise SystemExit(0)
            trip = get_trip(chosen)
            if trip is None:
                print(f"Поездка #{chosen} не найдена.")
                raise SystemExit(1)
            trip_id = int(trip["id"])
            city = trip["city"]
            dates = trip["dates"]
            origin_city = trip["origin_city"]
            user_message = trip.get("user_query") or "Обнови культурную программу поездки"
            prefs_data = get_preferences(trip_id)
            if prefs_data:
                prefs = TripPreferences.model_validate(prefs_data)
                search_context = _apply_preferences_to_session(prefs)
                preferences_dict = prefs.model_dump()
            else:
                search_context = ""
                preferences_dict = {}
                print("Предпочтения не найдены — поиск без опросника.")
            latest = get_latest_itinerary(trip_id)
            base_program = (
                normalize_stored_program(latest["program"]) if latest else None
            )
            if latest:
                print(
                    f"Последняя версия программы: v{latest['version']} "
                    f"({latest['scope']})"
                )
            rebuild_scope = _choose_rebuild_scope(has_program=base_program is not None)
            user_message = human_message_for_scope(rebuild_scope)
        else:
            city, dates, origin_city, user_message = _collect_new_trip_inputs()
            profile_data = get_user_profile()
            prefs = resolve_preferences_for_new_trip(
                has_profile=profile_data is not None,
                profile_data=profile_data,
            )
            preferences_dict = prefs.model_dump()
            search_context = _apply_preferences_to_session(prefs)
            save_user_profile(preferences_dict)
            trip_id = create_trip(city, dates, origin_city, user_message)
            save_preferences(trip_id, preferences_dict)
            print(f"Поездка сохранена в БД: id={trip_id}")

        update_trip_status(trip_id, "building")

        initial_state: AgentState = {
            "trip_id": trip_id,
            "city": city,
            "dates": dates,
            "origin_city": origin_city,
            "search_context": search_context,
            "preferences": preferences_dict,
            "rebuild_scope": rebuild_scope,
            "retry_count": 0,
            "approved": False,
            "critic_passed": False,
            "critic_notes": "",
            "messages": [HumanMessage(content=user_message)],
        }
        if base_program is not None:
            initial_state["base_program"] = base_program

        print(f"Режим пересборки: {rebuild_scope}")
        if rebuild_scope != "full":
            tools = required_tools_for_scope(rebuild_scope)
            if tools:
                print(f"  → веб-поиск: {', '.join(tools)}")
            else:
                print("  → без веб-поиска")

        final_state = _run_graph(initial_state)
        program = final_state.get("program")
        if program:
            version_id = save_itinerary_version(
                trip_id,
                program,
                scope=rebuild_scope,
                approved=bool(final_state.get("approved")),
            )
            print(f"\nПрограмма сохранена: trip_id={trip_id}, version_id={version_id}")
        else:
            print("\nПредупреждение: программа не попала в состояние графа.")

    except ValueError as exc:
        print(f"Ошибка валидации входа: {exc}")
        raise SystemExit(1) from exc
    except SystemExit:
        raise
    except Exception as exc:
        print(_format_runtime_error(exc))
        raise SystemExit(1) from exc
