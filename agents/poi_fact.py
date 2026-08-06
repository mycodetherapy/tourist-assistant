"""Туристическая справка по POI: только LLM (без веб-поиска и Wikipedia)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm import get_llm_chat
from search.poi_fact_sources import PoiFactContext

_MIN_CHARS = 300
_MAX_CHARS = 2200
_WIKI_MIN_CHARS = 40
POI_FACT_NOT_FOUND = "Справка по месту не найдена в Wikipedia"

_URL_RE = re.compile(r"https?://", re.I)
_BORING_CITY_RE = re.compile(
    r"(?i)(столица республики|административный центр городского округа|"
    r"население города|основан в \d{4} году во время)"
)
_ABSTRACT_FLUFF_RE = re.compile(
    r"(?i)(уникальн\w+\s+атмосфер|незабываем\w+\s+впечатлен|"
    r"стоит\s+обязательно\s+посетить|идеальное\s+место\s+для|"
    r"погрузиться\s+в\s+атмосфер|насладиться\s+красот)"
)
_FACT_HINT_RE = re.compile(
    r"(?i)(\d{3,4}\s*г\.?|век|основан|построен|открыт|архитектур|"
    r"стиль|памятник|музей|кремл|собор|театр|реставрац|назван|"
    r"присвоен|включён|UNESCO|метров|этаж)"
)
_YEAR_RE = re.compile(r"\d{3,4}")


def _trim_to_max(text: str) -> str:
    blob = (text or "").strip()
    if len(blob) <= _MAX_CHARS:
        return blob
    trimmed = blob[: _MAX_CHARS - 1].rsplit(" ", 1)[0]
    if trimmed.endswith((".", "!", "?", "…")):
        return trimmed
    return trimmed + "…"


def has_enough_poi_facts(text: str) -> bool:
    """Минимум фактической плотности: даты и конкретные детали."""
    blob = (text or "").strip()
    if not blob:
        return False
    fact_hits = len(_FACT_HINT_RE.findall(blob))
    year_hits = len(_YEAR_RE.findall(blob))
    return fact_hits >= 3 and year_hits >= 1


def is_valid_poi_fact(text: str) -> bool:
    blob = (text or "").strip()
    if len(blob) < _MIN_CHARS or len(blob) > _MAX_CHARS:
        return False
    if _URL_RE.search(blob):
        return False
    if blob.count("\n- ") >= 3 or blob.count("\n• ") >= 3:
        return False
    if not has_enough_poi_facts(blob):
        return False
    return True


def looks_like_city_article(text: str) -> bool:
    return bool(_BORING_CITY_RE.search((text or "").strip()))


def looks_like_abstract_fluff(text: str) -> bool:
    blob = (text or "").strip()
    if not blob:
        return True
    if _ABSTRACT_FLUFF_RE.search(blob) and not _FACT_HINT_RE.search(blob):
        return True
    abstract_hits = len(_ABSTRACT_FLUFF_RE.findall(blob))
    fact_hits = len(_FACT_HINT_RE.findall(blob))
    return abstract_hits >= 2 and fact_hits < 2


def poi_fact_user_prompt(*, name: str, city: str) -> str:
    place = (name or "Место").strip()
    town = (city or "").strip() or "городе"
    return (
        f"В городе {town} есть {place}. "
        f"Дай развёрнутую историческую справку: что это за объект, "
        f"когда основан/построен/открыт, кто заказчик или архитектор, "
        f"архитектурный стиль, ключевые события, реставрации и чем место известно."
    )


_SYSTEM_PROMPT = (
    "Ты — travel-редактор для туристов. Пиши на русском языке.\n\n"
    f"Формат: связный текст из 6–9 предложений ({_MIN_CHARS}–{_MAX_CHARS} символов).\n\n"
    "Нужно:\n"
    "— Только про указанное место (не общая справка о городе).\n"
    "— Конкретные факты: годы, имена, стиль, назначение, исторические события, реставрации.\n"
    "— Минимум 4 проверяемые детали (дата, архитектор/заказчик, событие, экспонаты, статус UNESCO).\n"
    "— Хотя бы одна дата (год основания, постройки, открытия или крупного события).\n"
    "— Тон: познавательный, фактологичный, без рекламного пафоса.\n\n"
    "Запрещено:\n"
    "— Абстракции вроде «уникальная атмосфера», «незабываемые впечатления», «стоит посетить».\n"
    "— URL, списки, советы про еду и бронирование.\n"
    "— Выдумывать точные даты и цифры, если не уверен — пиши обобщённо («в XVI веке»).\n"
    "— Пересказывать историю всего города вместо конкретной точки."
)

_RETRY_PROMPT = (
    "Ответ слишком короткий или абстрактный. "
    "Добавь факты: годы, архитектура, кто построил, реставрации, чем знаменито место."
)

_CITY_RETRY_PROMPT = (
    "Это похоже на справку о городе, а не о конкретном месте. "
    "Перепиши только про указанную достопримечательность с фактами."
)

_FLUFF_RETRY_PROMPT = (
    "Слишком много общих фраз. Перепиши с конкретными историческими фактами, "
    "датами, именами и событиями — без абстрактных эпитетов."
)


def generate_poi_fact_llm(*, name: str, city: str) -> str:
    llm = get_llm_chat().bind(max_tokens=2048)
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=poi_fact_user_prompt(name=name, city=city)),
    ]
    best = ""
    for attempt in range(3):
        response = llm.invoke(messages)
        content = getattr(response, "content", response)
        text = str(content).strip()
        if (
            is_valid_poi_fact(text)
            and not looks_like_city_article(text)
            and not looks_like_abstract_fluff(text)
        ):
            return text
        if text and (not best or len(text) > len(best)):
            best = text
        if attempt == 0:
            messages.append(response)
            messages.append(HumanMessage(content=_RETRY_PROMPT))
        elif attempt == 1:
            messages.append(response)
            if looks_like_city_article(text):
                messages.append(HumanMessage(content=_CITY_RETRY_PROMPT))
            else:
                messages.append(HumanMessage(content=_FLUFF_RETRY_PROMPT))

    if best:
        return _trim_to_max(best)
    raise RuntimeError("LLM не вернул текст справки по месту")


@dataclass(frozen=True)
class PoiFactResult:
    text: str
    used_llm: bool
    source_kind: str


def generate_poi_fact(ctx: PoiFactContext, *, use_llm: bool = True) -> PoiFactResult:
    if use_llm:
        text = generate_poi_fact_llm(name=ctx.name, city=ctx.city)
        return PoiFactResult(
            text=_trim_to_max(text),
            used_llm=True,
            source_kind="llm",
        )
    text = fetch_poi_fact_wikipedia(ctx)
    return PoiFactResult(
        text=_trim_to_max(text),
        used_llm=False,
        source_kind="wikipedia",
    )


def fetch_poi_fact_wikipedia(ctx: PoiFactContext) -> str:
    """Wikipedia/Wikidata без LLM для free tier."""
    qid = _resolve_poi_wikidata_qid(ctx)
    if qid:
        return _fetch_poi_fact_by_wikidata(qid)
    return _fetch_poi_fact_by_search(name=ctx.name, city=ctx.city)


def _resolve_poi_wikidata_qid(ctx: PoiFactContext) -> str | None:
    from search.osm.nominatim import resolve_city_center

    qid = (ctx.wikidata_qid or "").strip().upper() or None
    if not qid:
        return None
    town = (ctx.city or "").strip()
    if not town:
        return qid
    center = resolve_city_center(town)
    city_qid = ((center.wikidata_id or "").strip().upper() if center else "") or None
    if city_qid and qid == city_qid:
        return None
    return qid


def _fetch_poi_fact_by_wikidata(qid: str) -> str:
    """Статья по Wikidata QID — как для маршрутов из Wikidata, без Wikipedia-поиска."""
    from search.wikidata.city_description import (
        clean_wikipedia_plain,
        fetch_wikipedia_poi_for_wikidata,
    )

    text = clean_wikipedia_plain(
        fetch_wikipedia_poi_for_wikidata(qid, max_chars=_MAX_CHARS)
    )
    if text and len(text) >= _WIKI_MIN_CHARS:
        return text
    raise RuntimeError(POI_FACT_NOT_FOUND)


def _fetch_poi_fact_by_search(*, name: str, city: str) -> str:
    """POI из city pack без Wikidata-тега: только явная статья, не справка о городе."""
    from search.wikidata.city_description import (
        city_wikipedia_titles,
        clean_wikipedia_plain,
        fetch_wikipedia_poi_text,
        normalize_wiki_title,
        search_wikipedia_titles,
    )

    place = (name or "").strip()
    town = (city or "").strip()
    if not place:
        raise RuntimeError(POI_FACT_NOT_FOUND)

    blocked_titles = city_wikipedia_titles(town) if town else set()
    queries = [f"{place} {town}".strip(), place]
    seen_titles: set[str] = set()

    for query in queries:
        if not query:
            continue
        for title in search_wikipedia_titles(query=query, limit=8):
            norm = normalize_wiki_title(title)
            if norm in seen_titles or norm in blocked_titles:
                continue
            seen_titles.add(norm)
            if not _search_title_matches_place(title, place):
                continue
            text = clean_wikipedia_plain(
                fetch_wikipedia_poi_text(title=title, max_chars=_MAX_CHARS)
            )
            if len(text) < _WIKI_MIN_CHARS:
                continue
            if looks_like_city_article(text):
                continue
            return text

    raise RuntimeError(POI_FACT_NOT_FOUND)


def _significant_name_tokens(name: str) -> list[str]:
    stop = {
        "йошкар",
        "ола",
        "город",
        "улица",
        "площадь",
        "республика",
        "марий",
        "марийск",
        "центр",
        "район",
    }
    return [
        w
        for w in re.findall(r"[а-яёa-z]{4,}", (name or "").lower())
        if w not in stop
    ]


def _search_title_matches_place(title: str, place: str) -> bool:
    """Заголовок статьи должен относиться к POI, а не к городу."""
    from search.wikidata.city_description import normalize_wiki_title

    tokens = _significant_name_tokens(place)
    if not tokens:
        return True
    blob = normalize_wiki_title(title)
    for token in tokens:
        stem = token[:-1] if len(token) >= 6 and token[-1] in "ауюыиь" else token
        if token in blob or stem in blob:
            return True
    return False
