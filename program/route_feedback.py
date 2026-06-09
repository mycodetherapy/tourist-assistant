"""Лайкнутые маршруты: сохранение при пересборке и контекст для LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from db import list_item_feedback
from models.routes import PoiPoint, RouteMaterials, RouteProgram, TripRouteCase
from program.item_key import make_item_key
from program.parse_items import parse_program_sections

MAX_LIKED_ROUTES_PER_TRIP = 10
MAX_LIKED_ROUTE_STOPS_PER_TRIP = 40
NEW_ROUTE_BATCH_IDS = ("N-A", "N-B", "N-C")
_PRESERVED_MAX_OVERLAP = 0.5

_TAG_LABELS: dict[str, str] = {
    "landmarks": "достопримечательности",
    "parks": "парки",
    "museums": "музеи",
    "embankments": "набережные",
    "monuments": "памятники",
    "temples": "храмы и монастыри",
    "pedestrian_streets": "пешеходные улицы",
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
    preferred_poi_ids: frozenset[str] = frozenset()
    banned_poi_ids: frozenset[str] = frozenset()


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


def load_poi_stop_vote_sets(trip_id: int) -> tuple[set[str], set[str]]:
    """Лайкнутые и дизлайкнутые poi_id из секции route_stops."""
    from db.repository import list_item_feedback_by_section
    from program.item_key import parse_route_stop_key

    liked: set[str] = set()
    disliked: set[str] = set()
    for key, vote in list_item_feedback_by_section(trip_id, "route_stops").items():
        poi_id = parse_route_stop_key(key)
        if not poi_id:
            continue
        if vote == 1:
            liked.add(poi_id)
        elif vote == -1:
            disliked.add(poi_id)
    return liked, disliked


def count_liked_route_stops(trip_id: int) -> int:
    liked, _ = load_poi_stop_vote_sets(trip_id)
    return len(liked)


def rebuild_poi_preferences(
    trip_id: int,
    materials: RouteMaterials | None,
    preserved: list[TripRouteCase],
) -> tuple[set[str], set[str], set[str]]:
    """preferred, banned (hard), disliked (raw 👎 stops) для LLM и пост-процессора."""
    poi_liked, poi_disliked = load_poi_stop_vote_sets(trip_id)
    expanded_ban: set[str] = set(poi_disliked)
    if materials is not None:
        expanded_ban = expand_similar_banned_poi(
            materials.leisure_points, poi_disliked
        )
    banned = expanded_ban | collect_leisure_poi_ids(preserved)
    preferred = set(poi_liked) - banned
    if materials is not None:
        pool = {p.poi_id for p in materials.leisure_points}
        preferred &= pool
        banned &= pool
        expanded_ban &= pool
    return preferred, banned, poi_disliked


def expand_similar_banned_poi(
    leisure: list[PoiPoint],
    disliked_poi_ids: set[str],
) -> set[str]:
    """Дизлайк + POI того же типа с похожим названием."""
    from search.yandex.poi_filters import route_name_key

    banned = set(disliked_poi_ids)
    disliked = [p for p in leisure if p.poi_id in disliked_poi_ids]
    for anchor in disliked:
        akey = route_name_key(anchor.name)
        for poi in leisure:
            if poi.poi_id in banned:
                continue
            if poi.tag != anchor.tag:
                continue
            if route_name_key(poi.name) == akey:
                banned.add(poi.poi_id)
                continue
            if _names_share_theme(anchor.name, poi.name):
                banned.add(poi.poi_id)
    return banned


def _names_share_theme(a: str, b: str) -> bool:
    al, bl = a.lower(), b.lower()
    for keywords, _theme in _NAME_THEME_HINTS:
        hits = [kw for kw in keywords if kw in al or kw in bl]
        if len(hits) >= 2 or (hits and any(kw in al and kw in bl for kw in keywords)):
            return True
    shared = {w for w in al.split() if len(w) > 4} & {w for w in bl.split() if len(w) > 4}
    return len(shared) >= 1


def _describe_poi_stop_preferences(
    preferred: set[str],
    disliked: set[str],
    poi_index: dict[str, PoiPoint],
) -> list[str]:
    lines: list[str] = []
    if preferred:
        entries = [
            f"{poi_index[pid].name} [poi_id={pid}]"
            if pid in poi_index
            else f"poi_id={pid}"
            for pid in sorted(preferred)
        ]
        lines.append(
            "Лайкнутые остановки — включи эти poi_id в новые маршруты (или 1–2 похожих "
            "по типу из digest, если места не хватает): "
            + "; ".join(entries[:15])
        )
    if disliked:
        entries = [
            f"{poi_index[pid].name} [poi_id={pid}]"
            if pid in poi_index
            else f"poi_id={pid}"
            for pid in sorted(disliked)
        ]
        themes = _infer_soft_themes(
            [poi_index[pid].name for pid in disliked if pid in poi_index],
            {poi_index[pid].tag for pid in disliked if pid in poi_index},
        )
        lines.append(
            "Дизлайкнутые остановки — НЕ использовать эти poi_id и близкие по типу/названию: "
            + "; ".join(entries[:15])
        )
        if themes:
            lines.append(
                "Избегай похожих мотивов (не повторяй тип мест): " + "; ".join(themes)
            )
    return lines


def snapshot_route_feedback(
    base_program: dict[str, Any],
    trip_id: int,
    rebuild_scope: str,
) -> dict[str, Any] | None:
    """Снимок оценок в начале пересборки — до любых side-effect в UI."""
    ctx = build_route_feedback_context(
        base_program, trip_id, rebuild_scope=rebuild_scope
    )
    if ctx is None:
        return None
    return {
        "rebuild_scope": rebuild_scope,
        "llm_instructions": ctx.llm_instructions,
        "preferred_poi_ids": sorted(ctx.preferred_poi_ids),
        "banned_poi_ids": sorted(ctx.banned_poi_ids),
        "liked_cases": [c.model_dump() for c in ctx.liked_cases],
    }


def build_route_feedback_context(
    base_program: dict[str, Any],
    trip_id: int,
    *,
    rebuild_scope: str = "routes",
) -> RouteFeedbackContext | None:
    """Контекст для пересборки маршрутов: лайки, остановки, мягкие мотивы."""
    cases = _program_route_cases(base_program)
    votes = _route_votes_by_index(base_program, trip_id) if cases else {}
    liked: list[TripRouteCase] = []
    disliked: list[TripRouteCase] = []
    for index, case in enumerate(cases):
        vote = votes.get(index)
        if vote == 1:
            liked.append(case.model_copy(update={"preserved": True}))
        elif vote == -1:
            disliked.append(case)

    poi_liked, poi_disliked = load_poi_stop_vote_sets(trip_id)
    if not liked and not disliked and not poi_liked and not poi_disliked:
        return None

    poi_index = _load_poi_index(trip_id)
    from search.route_materials_store import load_route_materials_for_trip

    materials = load_route_materials_for_trip(trip_id)
    preserved_for_ban = liked if rebuild_scope == "routes" else []
    preferred, banned, poi_disliked = rebuild_poi_preferences(
        trip_id, materials, preserved_for_ban
    )
    preserve_liked = rebuild_scope == "routes" and bool(liked)
    forbidden_ids = sorted(
        (collect_leisure_poi_ids(liked) | banned) if preserve_liked else banned
    )

    parts: list[str] = [
        "\n--- Оценки пользователя по маршрутам и остановкам ---",
        "Шаг 1: по лайкам (маршруты и отдельные остановки) выведи общие мотивы.",
        "Шаг 2: подбери poi_id из materials_digest: лайкнутые остановки включай "
        "или заменяй похожими; дизлайкнутые poi_id не используй.",
    ]
    if preserve_liked:
        parts.append(
            "Жёсткое правило: poi_id из «запрещено» не использовать в новых A/B/C."
        )
    if liked:
        if preserve_liked:
            parts.append(
                f"Сохранённые лайкнутые варианты ({len(liked)}) останутся без изменений. "
                "Сгенерируй только 3 НОВЫх маршрута A/B/C."
            )
            parts.append(
                "Остановки-примеры из лайкнутых маршрутов (для вдохновения, не для копирования пути):"
            )
        else:
            parts.append(
                "Лайкнутые варианты — ориентир по параметрам (длина, число остановок, мотивы). "
                "Сгенерируй 3 новых маршрута A/B/C; poi_id можно менять, сохраняя дух подборки."
            )
            parts.append("Параметры лайкнутых маршрутов:")
            for case in liked:
                parts.append(_route_criteria_line(case))
            parts.append(
                "Примеры остановок из лайкнутых (для вдохновения, не копируй путь целиком):"
            )
        for case in liked:
            parts.extend(_describe_liked_case(case, poi_index))
        aggregate = _aggregate_liked_themes(liked, poi_index)
        if aggregate:
            parts.append(aggregate)
        if forbidden_ids and preserve_liked:
            parts.append(
                "Запрещённые poi_id (уже в сохранённых маршрутах): "
                + ", ".join(forbidden_ids)
            )
        if preserve_liked:
            parts.append(
                "Новые маршруты: тот же дух и разнообразие мотивов, но другие места "
                "(пересечение poi с лайками < 50%). Можешь комбинировать мотивы и "
                "добавлять неожиданные, но уместные точки из digest."
            )
        elif liked:
            parts.append(
                "Новые маршруты: похожий характер и длина, но свобода в выборе poi_id из digest."
            )
    if disliked:
        parts.append("Не понравились — ориентиры, чего не повторять:")
        for case in disliked:
            parts.extend(_describe_disliked_case(case, poi_index))
    parts.extend(_describe_poi_stop_preferences(preferred, poi_disliked, poi_index))
    return RouteFeedbackContext(
        liked_cases=tuple(liked[:MAX_LIKED_ROUTES_PER_TRIP]),
        llm_instructions="\n".join(parts) + "\n",
        preferred_poi_ids=frozenset(preferred),
        banned_poi_ids=frozenset(banned),
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
