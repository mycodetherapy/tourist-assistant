"""Лайкнутые маршруты: сохранение при пересборке и контекст для LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from db import list_item_feedback
from models.routes import PoiPoint, RouteProgram, TripRouteCase
from program.item_key import make_item_key
from program.parse_items import parse_program_sections

MAX_LIKED_ROUTES_PER_TRIP = 10
NEW_ROUTE_BATCH_IDS = ("N-A", "N-B", "N-C")
_PRESERVED_MAX_OVERLAP = 0.5

_TAG_LABELS: dict[str, str] = {
    "landmarks": "достопримечательности",
    "parks": "парки",
    "museums": "музеи",
    "embankments": "набережные",
    "monuments": "памятники",
    "exhibitions": "выставки",
    "galleries": "галереи",
    "philharmonic": "филармонии",
    "theaters": "театры",
}

# Мягкие мотивы по ключевым словам в названиях (подсказка LLM, не жёсткое правило).
_NAME_THEME_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("собор", "храм", "церк", "монаст", "часовн", "мечет", "синагог"), "культовая архитектура"),
    (("музей", "галере", "выстав"), "музеи и выставки"),
    (("парк", "сад", "сквер", "ботан"), "парки и зелёные зоны"),
    (("набереж", "река", "канал", "мост"), "набережные и водная линия"),
    (("памятник", "монумент", "скulpt"), "памятники и монументы"),
    (("театр", "филармон", "концерт"), "сценические площадки"),
    (("кремл", "крепост", "бастион", "креп"), "исторические ансамбли"),
    (("усадьб", "дворец", "особняк"), "архитектурные ансамбли"),
)


@dataclass(frozen=True)
class RouteFeedbackContext:
    """Лайкнутые маршруты и инструкции для writer при partial rebuild."""

    liked_cases: tuple[TripRouteCase, ...]
    llm_instructions: str


def _program_route_cases(program: dict[str, Any]) -> list[TripRouteCase]:
    raw = program.get("routes")
    if not isinstance(raw, dict):
        return []
    try:
        return list(RouteProgram.model_validate(raw).cases)
    except Exception:
        return []


def _route_votes_by_index(
    program: dict[str, Any],
    trip_id: int,
) -> dict[int, int]:
    """item_index -> vote для секции routes."""
    votes_by_key = list_item_feedback(trip_id)
    parsed = parse_program_sections(program)
    out: dict[int, int] = {}
    for index, text in enumerate(parsed.routes.items):
        key = make_item_key("routes", text)
        if key in votes_by_key:
            out[index] = int(votes_by_key[key])
    return out


def count_liked_routes(program: dict[str, Any], trip_id: int) -> int:
    votes = _route_votes_by_index(program, trip_id)
    return sum(1 for vote in votes.values() if vote == 1)


def extract_liked_routes(
    base_program: dict[str, Any],
    trip_id: int,
) -> list[TripRouteCase]:
    """Маршруты с 👍 из текущей программы (порядок как в UI)."""
    cases = _program_route_cases(base_program)
    if not cases:
        return []
    votes = _route_votes_by_index(base_program, trip_id)
    liked: list[TripRouteCase] = []
    for index, case in enumerate(cases):
        if votes.get(index) == 1:
            liked.append(case.model_copy(update={"preserved": True}))
    return liked[:MAX_LIKED_ROUTES_PER_TRIP]


def _load_poi_index(trip_id: int | None) -> dict[str, PoiPoint]:
    if trip_id is None:
        return {}
    from search.route_materials_store import load_route_materials_for_trip

    materials = load_route_materials_for_trip(trip_id)
    if materials is None:
        return {}
    return {p.poi_id: p for p in materials.leisure_points}


def _tag_label(tag: str) -> str:
    return _TAG_LABELS.get(tag, tag.replace("_", " "))


def _infer_soft_themes(
    stop_names: list[str],
    tags: set[str],
) -> list[str]:
    themes: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        label = _tag_label(tag)
        if label not in seen:
            themes.append(label)
            seen.add(label)
    blob = " ".join(stop_names).lower()
    for keywords, theme in _NAME_THEME_HINTS:
        if theme in seen:
            continue
        if any(kw in blob for kw in keywords):
            themes.append(theme)
            seen.add(theme)
    return themes


def _route_length_label(leisure_count: int) -> str:
    if leisure_count <= 3:
        return "компактный"
    if leisure_count <= 5:
        return "средний"
    return "длинный"


def _route_criteria_line(case: TripRouteCase) -> str:
    leisure = [s for s in case.stops if s.kind == "leisure"]
    title = (case.title or "").strip() or f"вариант {case.case_id}"
    return (
        f"- {title}: {_route_length_label(len(leisure))} маршрут, "
        f"~{len(leisure)} остановок, "
        f"краткое описание «{(case.summary or '')[:120]}»"
    )


def _describe_liked_case(
    case: TripRouteCase,
    poi_index: dict[str, PoiPoint],
) -> list[str]:
    """Строки промпта: остановки и мягкие мотивы одного лайкнутого маршрута."""
    leisure = [s for s in case.stops if s.kind == "leisure"]
    title = (case.title or "").strip() or f"вариант {case.case_id}"
    lines = [
        f"**{case.case_id}: {title}** "
        f"({_route_length_label(len(leisure))}, {len(leisure)} остановок):",
    ]
    stop_names: list[str] = []
    tags: set[str] = set()
    for stop in leisure:
        name = (stop.narrative or "").strip()
        if not name and stop.poi_id and stop.poi_id in poi_index:
            name = poi_index[stop.poi_id].name
        if not name:
            continue
        stop_names.append(name)
        poi = poi_index.get(stop.poi_id or "")
        if poi is not None:
            tags.add(poi.tag)
        tag_hint = f", {_tag_label(poi.tag)}" if poi is not None else ""
        lines.append(f"  • {name}{tag_hint}")

    themes = _infer_soft_themes(stop_names, tags)
    if themes:
        lines.append(
            "  Мягкие мотивы (ориентир, не обязательство): "
            + "; ".join(themes)
        )
    return lines


def _describe_disliked_case(
    case: TripRouteCase,
    poi_index: dict[str, PoiPoint],
) -> list[str]:
    lines = [_route_criteria_line(case)]
    stop_names = [
        (s.narrative or "").strip()
        for s in case.stops
        if s.kind == "leisure" and (s.narrative or "").strip()
    ]
    if stop_names:
        preview = "; ".join(stop_names[:5])
        if len(stop_names) > 5:
            preview += "…"
        lines.append(f"  Примеры остановок: {preview}")
    tags = {
        poi_index[s.poi_id].tag
        for s in case.stops
        if s.kind == "leisure" and s.poi_id and s.poi_id in poi_index
    }
    themes = _infer_soft_themes(stop_names, tags)
    if themes:
        lines.append(f"  Возможные мотивы (избегать похожего): {'; '.join(themes)}")
    return lines


def _aggregate_liked_themes(
    liked: list[TripRouteCase],
    poi_index: dict[str, PoiPoint],
) -> str:
    stop_names: list[str] = []
    tags: set[str] = set()
    for case in liked:
        for stop in case.stops:
            if stop.kind != "leisure":
                continue
            name = (stop.narrative or "").strip()
            if not name and stop.poi_id and stop.poi_id in poi_index:
                name = poi_index[stop.poi_id].name
            if name:
                stop_names.append(name)
            poi = poi_index.get(stop.poi_id or "")
            if poi is not None:
                tags.add(poi.tag)
    themes = _infer_soft_themes(stop_names, tags)
    if not themes:
        return ""
    return (
        "Сводные мотивы по всем лайкам (выведи свои и комбинируй свободно): "
        + "; ".join(themes)
    )


def build_route_feedback_context(
    base_program: dict[str, Any],
    trip_id: int,
) -> RouteFeedbackContext | None:
    """Контекст для partial rebuild routes: лайки, остановки, мягкие мотивы."""
    cases = _program_route_cases(base_program)
    if not cases:
        return None
    votes = _route_votes_by_index(base_program, trip_id)
    liked: list[TripRouteCase] = []
    disliked: list[TripRouteCase] = []
    for index, case in enumerate(cases):
        vote = votes.get(index)
        if vote == 1:
            liked.append(case.model_copy(update={"preserved": True}))
        elif vote == -1:
            disliked.append(case)

    if not liked and not disliked:
        return None

    poi_index = _load_poi_index(trip_id)
    forbidden_ids = sorted(collect_leisure_poi_ids(liked))

    parts: list[str] = [
        "\n--- Оценки пользователя по маршрутам ---",
        "Шаг 1: по остановкам лайков выведи общие мотивы (тип мест, настроение, темп).",
        "Шаг 2: подбери другие poi_id из materials_digest в том же духе — "
        "новые объекты, не копия сохранённых маршрутов.",
        "Жёсткое правило: poi_id из списка «запрещено» не использовать в новых A/B/C.",
    ]
    if liked:
        parts.append(
            f"Сохранённые лайкнутые варианты ({len(liked)}) останутся без изменений. "
            "Сгенерируй только 3 НОВЫх маршрута A/B/C."
        )
        parts.append(
            "Остановки-примеры из лайкнутых маршрутов (для вдохновения, не для копирования пути):"
        )
        for case in liked:
            parts.extend(_describe_liked_case(case, poi_index))
        aggregate = _aggregate_liked_themes(liked, poi_index)
        if aggregate:
            parts.append(aggregate)
        if forbidden_ids:
            parts.append(
                "Запрещённые poi_id (уже в сохранённых маршрутах): "
                + ", ".join(forbidden_ids)
            )
        parts.append(
            "Новые маршруты: тот же дух и разнообразие мотивов, но другие места "
            "(пересечение poi с лайками < 50%). Можешь комбинировать мотивы и "
            "добавлять неожиданные, но уместные точки из digest."
        )
    if disliked:
        parts.append("Не понравились — ориентиры, чего не повторять:")
        for case in disliked:
            parts.extend(_describe_disliked_case(case, poi_index))
    return RouteFeedbackContext(
        liked_cases=tuple(liked[:MAX_LIKED_ROUTES_PER_TRIP]),
        llm_instructions="\n".join(parts) + "\n",
    )


def collect_leisure_poi_ids(cases: list[TripRouteCase]) -> set[str]:
    out: set[str] = set()
    for case in cases:
        for stop in case.stops:
            if stop.kind == "leisure" and stop.poi_id:
                out.add(stop.poi_id)
    return out


def merge_preserved_with_new_routes(
    preserved: list[TripRouteCase],
    new_program: RouteProgram,
    *,
    new_case_ids: tuple[str, str, str] = NEW_ROUTE_BATCH_IDS,
) -> RouteProgram:
    """Лайкнутые сверху, затем 3 новых варианта с id N-A/N-B/N-C."""
    marked = [c.model_copy(update={"preserved": True}) for c in preserved]
    new_cases: list[TripRouteCase] = []
    for case, new_id in zip(new_program.cases[:3], new_case_ids):
        new_cases.append(
            case.model_copy(update={"case_id": new_id, "preserved": False})
        )
    return RouteProgram(
        materials_summary=new_program.materials_summary,
        cases=marked + new_cases,
    )
