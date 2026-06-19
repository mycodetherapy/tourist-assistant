"""Факт о городе: Wikidata/Wikipedia → живой LLM-текст для туриста."""

from __future__ import annotations

import re
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage

from agents.llm import get_llm
from search.wikidata.city_description import fetch_raw_city_fact

CityFactStatus = Literal["pending", "ready", "failed", "skipped"]

_MIN_CHARS = 80
_MAX_CHARS = 520

_URL_RE = re.compile(r"https?://", re.I)
_MUSEUM_LIST_RE = re.compile(
    r"(?im)(ресторан|кафе|бронируйте|обувь|tripadvisor)"
)
_BORING_RE = re.compile(
    r"(?i)(административн\w+\s+центр|является\s+(?:административн\w+\s+)?центром|"
    r"крупн\w+\s+город\s+на\s+(?:запад|восток|север|юг)е|"
    r"\u043d\u0430\u0441\u0435\u043b\u0435\u043d\u0438\w+|области\s+россии|центр\s+\w+\s+област)"
)


def is_boring_city_fact(text: str) -> bool:
    """Сухая справка без туристического угла."""
    blob = (text or "").strip()
    if not blob:
        return True
    boring_hits = len(_BORING_RE.findall(blob))
    if boring_hits >= 2:
        return True
    if boring_hits == 1 and len(blob) < 180:
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


def is_valid_city_fact(text: str) -> bool:
    """80–520 символов, без URL/списков и без административной «воды»."""
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
    return True


def _fallback_fact(city: str, raw: str) -> str:
    """Без LLM: вырезает туристически полезный фрагмент из Wikipedia lead."""
    text = (raw or "").strip()
    wiki_match = re.search(r"(?m)^Wikipedia:\s*(.+)$", text)
    if wiki_match:
        text = wiki_match.group(1).strip()
    else:
        text = re.sub(r"(?m)^(Город|Известные места|Wikidata|Регион):.*$", "", text).strip()

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

    parts = re.split(r"(?<=[.!?…])\s+", text)
    short = " ".join(parts[:3]).strip()
    if len(short) < _MIN_CHARS and len(parts) > 3:
        short = " ".join(parts[:4]).strip()
    if len(short) > _MAX_CHARS:
        short = short[: _MAX_CHARS - 1].rsplit(" ", 1)[0] + "."
    if len(short) < _MIN_CHARS:
        short = f"{city}: {short}"[:_MAX_CHARS]
    return short.strip()


_SYSTEM_PROMPT = (
    "Ты — travel-редактор. Напиши для туриста 2–3 живых предложения о городе "
    f"({_MIN_CHARS}–{_MAX_CHARS} символов, русский).\n\n"
    "Нужно:\n"
    "— Зачем ехать: история, архитектура, природа, атмосфера, характерные места.\n"
    "— Упомяни 1–2 конкретных места или черты из источника, если они есть.\n"
    "— Тон: вдохновляющий, но без рекламного пафоса.\n\n"
    "Запрещено:\n"
    "— «административный центр», «крупный город на … России», население, экономика.\n"
    "— URL, маркированные списки, советы про обувь и бронирование.\n"
    "— Выдумывать даты, цифры и названия мест, которых нет во входе.\n"
    "— Пересказывать сухую справку из Wikidata дословно.\n\n"
    "Если во входе мало фактов — опирайся на общеизвестные туристические черты города, "
    "но без вымышленных деталей."
)

_RETRY_PROMPT = (
    "Предыдущий вариант был слишком сухим (административная справка). "
    "Перепиши: акцент на прогулки, историю, архитектуру и места из источника. "
    "Без фраз про «административный центр» и «крупный город»."
)


def polish_city_fact_llm(raw: str, *, city: str) -> str:
    """Короткий LLM-вызов: живой туристический текст на русском."""
    llm = get_llm()
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=f"Город: {city}\n\nИсточник:\n{raw}"),
    ]
    for attempt in range(2):
        response = llm.invoke(messages)
        content = getattr(response, "content", response)
        text = str(content).strip()
        if is_valid_city_fact(text):
            return text
        if attempt == 0:
            messages.append(response)
            messages.append(HumanMessage(content=_RETRY_PROMPT))
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
