"""Факт о городе: Wikidata/Wikipedia → живой LLM-текст для туриста."""

from __future__ import annotations

import re
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm import get_llm_chat
from search.wikidata.city_description import fetch_raw_city_fact

CityFactStatus = Literal["pending", "ready", "failed", "skipped"]

_MIN_CHARS = 280
_MAX_CHARS = 2200

_URL_RE = re.compile(r"https?://", re.I)
_MUSEUM_LIST_RE = re.compile(
    r"(?im)(ресторан|кафе|бронируйте|обувь|tripadvisor)"
)
_BORING_RE = re.compile(
    r"(?i)(административн\w+\s+центр|является\s+(?:административн\w+\s+)?центром|"
    r"крупн\w+\s+город\s+на\s+(?:запад|восток|север|юг)е|"
    r"\u043d\u0430\u0441\u0435\u043b\u0435\u043d\u0438\w+|области\s+россии|центр\s+\w+\s+област)"
)
_ABSTRACT_FLUFF_RE = re.compile(
    r"(?i)(уникальн\w+\s+атмосфер|незабываем\w+\s+впечатлен|"
    r"идеальн\w+\s+место|погрузиться\s+в\s+атмосфер|насладиться\s+красот)"
)
_FACT_HINT_RE = re.compile(
    r"(?i)(\d{3,4}\s*г\.?|век|основан|переименован|столица|кремл|собор|"
    r"музей|театр|набереж|памятник|UNESCO|ханств|присоединен|войн)"
)
_YEAR_RE = re.compile(r"\d{3,4}")


def is_boring_city_fact(text: str) -> bool:
    """Сухая справка без туристического угла."""
    blob = (text or "").strip()
    if not blob:
        return True
    boring_hits = len(_BORING_RE.findall(blob))
    if boring_hits >= 2:
        return True
    if boring_hits == 1 and len(blob) < 280:
        return True
    admin_only = re.fullmatch(
        r"(?is).*(?:административн\w+\s+центр|является\s+центром).*",
        blob,
    )
    if admin_only and not re.search(
        r"(?i)(музе|парк|собор|кремл|набереж|театр|памятник|крепост|"
        r"истори|архитектур|прогул|центр\s+города|достопримечатель)",
        blob,
    ):
        return True
    return False


def has_enough_city_facts(text: str) -> bool:
    blob = (text or "").strip()
    if not blob:
        return False
    fact_hits = len(_FACT_HINT_RE.findall(blob))
    year_hits = len(_YEAR_RE.findall(blob))
    return fact_hits >= 3 and year_hits >= 1


def is_valid_city_fact(text: str) -> bool:
    """280–1400 символов, факты без административной «воды» и абстракций."""
    blob = (text or "").strip()
    if len(blob) < _MIN_CHARS or len(blob) > _MAX_CHARS:
        return False
    if _URL_RE.search(blob):
        return False
    if blob.count("\n- ") >= 2 or blob.count("\n• ") >= 2:
        return False
    if _MUSEUM_LIST_RE.search(blob) and len(re.findall(r"(?m)^\s*[-•]", blob)) >= 2:
        return False
    if is_boring_city_fact(blob):
        return False
    if looks_like_abstract_city_fact(blob):
        return False
    if not has_enough_city_facts(blob):
        return False
    return True


def looks_like_abstract_city_fact(text: str) -> bool:
    blob = (text or "").strip()
    if _ABSTRACT_FLUFF_RE.search(blob) and not _FACT_HINT_RE.search(blob):
        return True
    abstract_hits = len(_ABSTRACT_FLUFF_RE.findall(blob))
    fact_hits = len(_FACT_HINT_RE.findall(blob))
    return abstract_hits >= 2 and fact_hits < 2


def _fallback_fact(city: str, raw: str) -> str:
    """Без LLM: связный текст из Wikipedia lead без обрыва на «…»."""
    from search.wikidata.city_description import clean_wikipedia_plain

    text = (raw or "").strip()
    wiki_match = re.search(r"(?m)^Wikipedia:\s*(.+)$", text, re.S)
    if wiki_match:
        text = wiki_match.group(1).strip()
    else:
        text = re.sub(r"(?m)^(Город|Известные места|Wikidata|Регион):.*$", "", text).strip()

    text = clean_wikipedia_plain(text)

    if not text:
        landmarks = re.search(r"Известные места \(Wikidata\):\s*(.+)$", raw or "", re.M)
        if landmarks:
            names = landmarks.group(1).split(",")[:2]
            places = " и ".join(n.strip() for n in names if n.strip())
            text = (
                f"{city} привлекает прогулками по историческому центру "
                f"и местами вроде {places}."
            )
        else:
            text = (
                f"{city} — город для неспешных прогулок по центру "
                f"и знакомства с местной историей."
            )

    parts = [p.strip() for p in re.split(r"(?<=[.!?…])\s+", text) if p.strip()]
    parts = [p for p in parts if not p.startswith("==")]
    short = " ".join(parts[:10]).strip()
    if len(short) < _MIN_CHARS and len(parts) > 10:
        short = " ".join(parts[:14]).strip()
    if len(short) > _MAX_CHARS:
        short = short[:_MAX_CHARS].rsplit(" ", 1)[0].strip()
        if short and short[-1].isalnum():
            short = short.rstrip(".,;:") + "."
    if len(short) < _MIN_CHARS:
        short = f"{city}: {short}"[:_MAX_CHARS]
    return short.strip()


_SYSTEM_PROMPT = (
    "Ты — travel-редактор. Напиши для туриста фактологичный текст о городе "
    f"({_MIN_CHARS}–{_MAX_CHARS} символов, русский, 6–8 предложений).\n\n"
    "Нужно:\n"
    "— Исторические факты: год основания, переименования, ключевые эпохи и войны (с датами из источника).\n"
    "— 3–4 конкретных места или черты города из источника (кремль, собор, набережная, музей…).\n"
    "— Чем город знаменит в истории региона — через события и даты, а не общие эпитеты.\n"
    "— Хотя бы 2 года или века в тексте.\n"
    "— Тон: познавательный, без рекламного пафоса.\n\n"
    "Запрещено:\n"
    "— «административный центр», «крупный город на … России», население, экономика.\n"
    "— Абстракции: «уникальная атмосфера», «незабываемые впечатления», «идеальное место».\n"
    "— URL, маркированные списки, советы про обувь и бронирование.\n"
    "— Выдумывать даты, цифры и названия мест, которых нет во входе.\n"
    "— Пересказывать сухую справку из Wikidata дословно.\n\n"
    "Если во входе мало фактов — используй общеизвестные исторические черты города, "
    "но без вымышленных деталей."
)

_RETRY_PROMPT = (
    "Предыдущий вариант слишком общий или административный. "
    "Перепиши: больше дат, войн, переименований и конкретных мест из источника. "
    "Без фраз про «административный центр» и «уникальную атмосферу»."
)

_FACT_RETRY_PROMPT = (
    "Добавь исторические факты: когда основан город, ключевые события, "
    "какие достопримечательности упомянуть. Меньше абстрактных описаний, больше дат."
)


def polish_city_fact_llm(raw: str, *, city: str) -> str:
    """Короткий LLM-вызов: живой туристический текст на русском."""
    llm = get_llm_chat().bind(max_tokens=2048)
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=f"Город: {city}\n\nИсточник:\n{raw}"),
    ]
    for attempt in range(3):
        response = llm.invoke(messages)
        content = getattr(response, "content", response)
        text = str(content).strip()
        if is_valid_city_fact(text):
            return text
        if attempt == 0:
            messages.append(response)
            messages.append(HumanMessage(content=_RETRY_PROMPT))
        elif attempt == 1:
            messages.append(response)
            messages.append(HumanMessage(content=_FACT_RETRY_PROMPT))
    return _fallback_fact(city, raw)


def generate_city_fact(*, city: str, use_llm: bool = True) -> str:
    """Полный pipeline: raw → polish (или fallback)."""
    raw = fetch_raw_city_fact(city)
    if use_llm:
        try:
            return polish_city_fact_llm(raw, city=city)
        except Exception:
            pass
    fact = _fallback_fact(city, raw)
    if is_valid_city_fact(fact):
        return fact
    padded = f"{city}: {fact}"
    return padded[:_MAX_CHARS].strip()
