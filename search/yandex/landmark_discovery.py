"""Поиск названий достопримечательностей в вебе → match к OSM/Wikidata пулу."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from models.routes import LeisureTag
from search.web import format_search_digest, web_search_multi
from search.yandex.leisure_tags import infer_leisure_tag
from search.yandex.poi_filters import is_city_only_name, looks_like_leisure_poi

_MAX_CANDIDATES = 24
_MAX_TRACE_RESULTS = 12
_MAX_SNIPPET_LEN = 320
_MIN_NAME_LEN = 4
_MAX_NAME_LEN = 90

_SKIP_NAME_RE = re.compile(
    r"(что посмотрет|достопримечательност|лучшие мест|топ[-\s]?\d|"
    r"гид по|маршрут по|экскурс|wiki|википед|tripadvisor|"
    r"отзыв|рейтинг|фото|видео|как добраться|режим работы|"
    r"официальный сайт|билет|спектакл)",
    re.IGNORECASE,
)

_JUNK_PREFIX_RE = re.compile(
    r"^(?:visit|and|the|включают|начать|пока|после|второй|вечером|утром|"
    r"затем|можно|стоит|надпись|ычных|но и|а также|е оперы|театрам|"
    r"а за|ок |в поселке|главные|парков и|в центр|многие|обычно|"
    r"город с|старинный|республики|театрам и|окрестност|"
    r"^и\s+|имеет|включают|популярн)",
    re.IGNORECASE,
)

_INCOMPLETE_NOUN_RE = re.compile(
    r"^(?:музе(?:и|ев|ям|я|ями)|театр(?:а|ам|ами)?|площад(?:ей|ям|ями)?)$",
    re.IGNORECASE,
)

_DATE_NEWS_RE = re.compile(r"(\d{4}|риа новости|\.ru\b|https?://)", re.IGNORECASE)

_NAMED_SPOT_RES = (
    re.compile(r"набережн(?:ая|ой|ую)\s+[\w«»\"'-]+", re.IGNORECASE),
    re.compile(
        r"(?:Национальн\w+\s+){0,2}(?:художественн\w+\s+)?галере\w+(?:\s+[\w«»\"'-]+){0,3}",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:Национальн\w+\s+){0,2}музе\w+(?:\s+[\w«»\"'-]+){0,3}",
        re.IGNORECASE,
    ),
    re.compile(r"Царевококшайск\w+\s+кремл\w+", re.IGNORECASE),
    re.compile(r"[\w-]+\s+слобод\w+", re.IGNORECASE),
    re.compile(r"[\w-]+\s+собор", re.IGNORECASE),
    re.compile(r"[\w-]+\s+площад\w+", re.IGNORECASE),
    re.compile(r"[\w-]+\s+театр\w*", re.IGNORECASE),
    re.compile(r"Центральный\s+парк[\w\s«»\"'-]*", re.IGNORECASE),
    re.compile(r"парк\s+культуры[\w\s«»\"'-]*", re.IGNORECASE),
)

_AFTER_VERB_RE = re.compile(
    r"(?:посетить|перейти\s+к|осмотреть|направиться\s+к|"
    r"прогулк(?:а|и)\s+(?:по|к)|через)\s+([^.·,\n]{4,70})",
    re.IGNORECASE,
)

_LANDMARK_NAME_RE = re.compile(
    r"(?:"
    r"[«\"]([^»\"]{3,80})[»\"]|"
    r"(\d{1,2}[\.\)]\s*([^\n,;|·]{3,80}))"
    r")",
    re.MULTILINE,
)

_HINT_TAIL_RE = re.compile(
    r"([^\n,;|·]{2,80}(?:"
    r"музе(?:й|я|и)|галере(?:я|и)|"
    r"парк(?:а|у|ом|е|и)?|"
    r"площад(?:ь|и)|"
    r"набереж(?:ная|ной|ную|ной)?|"
    r"кремл(?:ь|я|ю|ём)?|"
    r"собор(?:а|у|ом)?|"
    r"храм(?:а|у|ом)?|"
    r"монаст(?:ырь|ыря|ырю)?|"
    r"памятник(?:а|у|ом)?|"
    r"монумент(?:а|у|ом)?|"
    r"театр(?:а|у|ом)?|"
    r"сквер(?:а|у|ом)?|"
    r"усадьб(?:а|ы|е|у)?|"
    r"мемориал(?:а|у|ом)?|"
    r"фонтан(?:а|у|ом)?|"
    r"дворец(?:а|у|ом)?|"
    r"колокольн(?:я|и|ю|ей)?|"
    r"каланч(?:а|у|ой|ей)?|"
    r"ряды|"
    r"слобод(?:а|ы|е|у)?|"
    r"заповедник(?:а|у|ом)?|"
    r"башн(?:я|и|ю|ей)?|"
    r"мост(?:а|у|ом)?|"
    r"костел(?:а|у|ом)?|"
    r"церк(?:овь|ви)|"
    r"часовн(?:я|и|ю|ей)?|"
    r"филармон(?:ия|ии|ию)?|"
    r"выстав(?:очный|ка|ки)|"
    r"дендропарк|"
    r"ботаническ(?:ий|ого)\s+сад"
    r"))",
    re.IGNORECASE,
)

_TITLE_SPLIT_RE = re.compile(r"\s*[—–\-|:]\s*")


@dataclass
class LandmarkDiscoveryTrace:
    """Метаданные веб-поиска для LangGraph / tool JSON."""

    provider: str = ""
    queries: list[str] = field(default_factory=list)
    results_count: int = 0
    raw_results_count: int = 0
    filter_fallback: bool = False
    answer: str | None = None
    search_results: list[dict[str, str | None]] = field(default_factory=list)
    landmark_names: list[str] = field(default_factory=list)
    geocode_queries: list[dict[str, str]] = field(default_factory=list)
    matched_pois: list[dict[str, str | float]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "queries": self.queries,
            "results_count": self.results_count,
            "raw_results_count": self.raw_results_count,
            "filter_fallback": self.filter_fallback,
            "answer": self.answer,
            "search_results": self.search_results,
            "landmark_names": self.landmark_names,
            "geocode_queries": self.geocode_queries,
            "matched_pois": self.matched_pois,
        }


def _trim_search_results(
    results: list[dict[str, str | None]],
    *,
    limit: int = _MAX_TRACE_RESULTS,
) -> list[dict[str, str | None]]:
    trimmed: list[dict[str, str | None]] = []
    for item in results[:limit]:
        snippet = str(item.get("snippet") or "")
        if len(snippet) > _MAX_SNIPPET_LEN:
            snippet = snippet[: _MAX_SNIPPET_LEN - 1] + "…"
        trimmed.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "snippet": snippet or None,
            }
        )
    return trimmed


def format_landmark_discovery_digest(trace: LandmarkDiscoveryTrace) -> str:
    """Текстовая сводка discovery для трейса и LLM."""
    lines: list[str] = []
    lines.append(
        f"Веб-поиск достопримечательностей ({trace.provider or 'unknown'}): "
        f"{trace.results_count} ссылок после фильтра "
        f"(до фильтра: {trace.raw_results_count})."
    )
    if trace.queries:
        lines.append("Запросы:")
        for index, query in enumerate(trace.queries, start=1):
            lines.append(f"  Q{index}. {query}")
    if trace.answer:
        answer = trace.answer.strip()
        if len(answer) > 600:
            answer = answer[:599] + "…"
        lines.append(f"Answer (Tavily): {answer}")
    if trace.search_results:
        lines.append("Сниппеты:")
        lines.append(format_search_digest(trace.search_results))
    lines.append(f"Извлечённые названия для match: {len(trace.landmark_names)}.")
    if trace.matched_pois:
        lines.append(f"Сопоставлено с OSM/Wikidata: {len(trace.matched_pois)}.")
        for index, item in enumerate(trace.matched_pois, start=1):
            lines.append(
                f"  M{index}. {item['discovery_name']} → "
                f"{item['poi_name']} (poi_id={item['poi_id']}, score={item['score']})"
            )
    elif trace.geocode_queries:
        for index, item in enumerate(trace.geocode_queries, start=1):
            lines.append(
                f"  N{index}. {item['name']} → query={item['query']!r}"
            )
    return "\n".join(lines)


def landmark_search_queries(city: str) -> list[str]:
    return [
        f"достопримечательности {city} что посмотреть за 1-2 дня",
        f"главные места {city} пешая прогулка",
        f"музеи парки площади {city} список",
    ]


def _city_in_name(name: str, city: str) -> bool:
    city_norm = city.lower().replace("ё", "е").strip()
    name_norm = name.lower().replace("ё", "е")
    if city_norm in name_norm:
        return True
    stem = city_norm.split("-")[0]
    return len(stem) >= 4 and stem in name_norm


def geocode_query_for_name(name: str, city: str) -> str:
    """Текст запроса в Geocoder для конкретного места."""
    cleaned = _clean_candidate(name, city)
    if not cleaned:
        return ""
    if _city_in_name(cleaned, city):
        return cleaned
    return f"{cleaned} {city}"


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_place_name(name: str) -> str:
    name = re.sub(r"\bнабережной\b", "набережная", name, flags=re.IGNORECASE)
    name = re.sub(r"\bнабережную\b", "набережная", name, flags=re.IGNORECASE)
    name = re.sub(r"^на\s+", "", name, flags=re.IGNORECASE)
    return _normalize_spaces(name)


def _split_compound(raw: str) -> list[str]:
    parts = re.split(r"\s+и\s+", raw)
    if len(parts) <= 1:
        return [raw]
    return [part.strip() for part in parts if part.strip()]


def _clean_candidate(raw: str, city: str) -> str:
    name = _normalize_place_name(raw.strip(" \t\n\r-–—•·|"))
    name = re.sub(r"^[\d\.\)\(]+\s*", "", name)
    name = name.strip("«»\"' ")
    if not name or len(name) < _MIN_NAME_LEN or len(name) > _MAX_NAME_LEN:
        return ""
    if _JUNK_PREFIX_RE.search(name):
        return ""
    if _INCOMPLETE_NOUN_RE.search(name):
        return ""
    if _DATE_NEWS_RE.search(name):
        return ""
    if len(name.split()) > 12:
        return ""
    generic_single = {"парк", "музей", "набережная", "сквер", "театр", "собор", "храм", "кремль"}
    if len(name.split()) == 1 and name.lower().replace("ё", "е") in generic_single:
        return ""
    if _SKIP_NAME_RE.search(name):
        return ""
    if is_city_only_name(name, city_hint=city):
        return ""
    if not looks_like_leisure_poi(name):
        return ""
    return name


def _extract_from_text(text: str, city: str) -> list[str]:
    found: list[str] = []
    for pattern in _NAMED_SPOT_RES:
        for match in pattern.finditer(text):
            for part in _split_compound(match.group(0)):
                cleaned = _clean_candidate(part, city)
                if cleaned:
                    found.append(cleaned)
    for match in _AFTER_VERB_RE.finditer(text):
        for part in _split_compound(match.group(1)):
            cleaned = _clean_candidate(part, city)
            if cleaned:
                found.append(cleaned)
    for match in _LANDMARK_NAME_RE.finditer(text):
        for group in match.groups():
            if not group:
                continue
            for part in _split_compound(group):
                cleaned = _clean_candidate(part, city)
                if cleaned:
                    found.append(cleaned)
    for line in text.splitlines():
        line = re.sub(r"^\d{1,2}[\.\)]\s*", "", line.strip())
        for part in _split_compound(line):
            cleaned = _clean_candidate(part, city)
            if cleaned:
                found.append(cleaned)
    for match in _HINT_TAIL_RE.finditer(text):
        tail = match.group(1)
        # Берём короткий хвост вокруг ключевого слова, а не всё предложение.
        for pattern in _NAMED_SPOT_RES:
            sub = pattern.search(tail)
            if sub:
                cleaned = _clean_candidate(sub.group(0), city)
                if cleaned:
                    found.append(cleaned)
                    break
        else:
            cleaned = _clean_candidate(tail, city)
            if cleaned and len(tail.split()) <= 6:
                found.append(cleaned)
    return found


def _extract_from_title(title: str, city: str) -> list[str]:
    parts = _TITLE_SPLIT_RE.split(title, maxsplit=1)
    candidates = [parts[0]]
    if len(parts) > 1:
        candidates.append(parts[1])
    out: list[str] = []
    for part in candidates:
        cleaned = _clean_candidate(part, city)
        if cleaned:
            out.append(cleaned)
        out.extend(_extract_from_text(part, city))
    return out


def extract_landmark_names(
    search_payload: dict[str, Any],
    *,
    city: str,
    max_names: int = _MAX_CANDIDATES,
) -> list[str]:
    """Список уникальных названий из digest веб-поиска."""
    seen: set[str] = set()
    ordered: list[str] = []

    def add(raw: str) -> None:
        cleaned = _clean_candidate(raw, city)
        if not cleaned:
            return
        key = cleaned.lower().replace("ё", "е")
        if key in seen:
            return
        seen.add(key)
        ordered.append(cleaned)

    answer = search_payload.get("answer")
    if answer:
        for name in _extract_from_text(str(answer), city):
            add(name)

    for item in search_payload.get("results") or []:
        title = str(item.get("title") or "")
        snippet = str(item.get("snippet") or "")
        for name in _extract_from_title(title, city):
            add(name)
        for name in _extract_from_text(snippet, city):
            add(name)
        if len(ordered) >= max_names:
            break

    return ordered[:max_names]


def run_landmark_discovery(
    city: str,
    *,
    max_names: int = _MAX_CANDIDATES,
) -> tuple[list[str], LandmarkDiscoveryTrace]:
    """Веб-поиск → названия + trace для LangGraph."""
    queries = landmark_search_queries(city)
    payload = web_search_multi(queries, kind="landmarks", cities=[city])
    names = extract_landmark_names(payload, city=city, max_names=max_names)
    geocode_queries = [
        {"name": name, "query": query}
        for name in names
        if (query := geocode_query_for_name(name, city))
    ]
    trace = LandmarkDiscoveryTrace(
        provider=str(payload.get("provider") or ""),
        queries=list(payload.get("queries") or queries),
        results_count=int(payload.get("results_count") or 0),
        raw_results_count=int(payload.get("raw_results_count") or 0),
        filter_fallback=bool(payload.get("filter_fallback")),
        answer=str(payload["answer"]) if payload.get("answer") else None,
        search_results=_trim_search_results(list(payload.get("results") or [])),
        landmark_names=names,
        geocode_queries=geocode_queries,
    )
    return names, trace


def infer_tag_for_name(name: str) -> LeisureTag:
    return infer_leisure_tag(name)
