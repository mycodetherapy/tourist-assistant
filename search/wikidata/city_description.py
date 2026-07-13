"""Туристический контекст о городе: Wikipedia, Wikidata, топ POI."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from search.osm.nominatim import CityCenter, resolve_city_center
from search.wikidata.places import fetch_top_landmark_names

_USER_AGENT = "tourist-assistant/1.0 (city-fact; local dev)"
_WIKI_LEAD_MAX = 900
_ADMIN_DESCRIPTION_RE = re.compile(
    r"(?i)(административн\w+\s+центр|центр\s+\w+\s+област|"
    r"город\s+(?:в|на)\s+\w+\s+(?:област|края|республик)|"
    r"city in .+ oblast|administrative center)"
)


def _entity_data_url(wikidata_id: str) -> str:
    qid = wikidata_id if wikidata_id.startswith("Q") else f"Q{wikidata_id}"
    return f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"


def _fetch_entity(wikidata_id: str) -> dict[str, Any] | None:
    if not wikidata_id:
        return None
    try:
        req = Request(
            _entity_data_url(wikidata_id),
            headers={"User-Agent": _USER_AGENT},
        )
        with urlopen(req, timeout=12) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    entities = payload.get("entities") if isinstance(payload, dict) else None
    if not isinstance(entities, dict):
        return None
    entity = next(iter(entities.values()), None)
    return entity if isinstance(entity, dict) else None


def fetch_wikidata_description(wikidata_id: str, *, lang: str = "ru") -> str:
    """Описание сущности (schema:description) на указанном языке."""
    entity = _fetch_entity(wikidata_id)
    if entity is None:
        return ""
    descriptions = entity.get("descriptions")
    if not isinstance(descriptions, dict):
        return ""
    for code in (lang, "ru", "en"):
        block = descriptions.get(code)
        if isinstance(block, dict):
            text = str(block.get("value") or "").strip()
            if text:
                return text
    return ""


def _sitelink_title(entity: dict[str, Any], site: str) -> str:
    sitelinks = entity.get("sitelinks")
    if not isinstance(sitelinks, dict):
        return ""
    block = sitelinks.get(site)
    if isinstance(block, dict):
        return str(block.get("title") or "").strip()
    return ""


def fetch_wikipedia_lead(*, title: str, lang: str = "ru") -> str:
    """Первый абзац статьи Wikipedia (REST summary API)."""
    title = (title or "").strip()
    if not title:
        return ""
    encoded = quote(title.replace(" ", "_"), safe="")
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{encoded}"
    try:
        req = Request(url, headers={"User-Agent": _USER_AGENT})
        with urlopen(req, timeout=12) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        return ""
    if not isinstance(payload, dict):
        return ""
    extract = str(payload.get("extract") or "").strip()
    if len(extract) > _WIKI_LEAD_MAX:
        extract = extract[:_WIKI_LEAD_MAX].rsplit(" ", 1)[0] + "…"
    return extract


def search_wikipedia_titles(
    *,
    query: str,
    lang: str = "ru",
    limit: int = 5,
) -> list[str]:
    """Поиск статей Wikipedia по запросу (MediaWiki API)."""
    q = (query or "").strip()
    if not q:
        return []
    url = (
        f"https://{lang}.wikipedia.org/w/api.php?"
        "action=query&list=search&format=json&utf8=1"
        f"&srsearch={quote(q)}&srlimit={max(1, min(limit, 10))}"
    )
    try:
        req = Request(url, headers={"User-Agent": _USER_AGENT})
        with urlopen(req, timeout=12) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        return []
    query_block = payload.get("query") if isinstance(payload, dict) else None
    search = query_block.get("search") if isinstance(query_block, dict) else None
    if not isinstance(search, list):
        return []
    titles: list[str] = []
    for hit in search:
        if isinstance(hit, dict):
            title = str(hit.get("title") or "").strip()
            if title:
                titles.append(title)
    return titles


def fetch_wikipedia_extract(
    *,
    title: str,
    lang: str = "ru",
    max_chars: int = 1200,
) -> str:
    """Вводный фрагмент статьи Wikipedia (plain text, включая «История»)."""
    title = (title or "").strip()
    if not title:
        return ""
    url = (
        f"https://{lang}.wikipedia.org/w/api.php?"
        "action=query&format=json&utf8=1&explaintext=1"
        f"&prop=extracts&exchars={max(400, min(max_chars, 2400))}"
        f"&titles={quote(title)}"
    )
    try:
        req = Request(url, headers={"User-Agent": _USER_AGENT})
        with urlopen(req, timeout=12) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        return ""
    pages = payload.get("query", {}).get("pages") if isinstance(payload, dict) else None
    if not isinstance(pages, dict):
        return ""
    page = next(iter(pages.values()), None)
    if not isinstance(page, dict):
        return ""
    extract = str(page.get("extract") or "").strip()
    if len(extract) > max_chars:
        extract = extract[:max_chars].rsplit(" ", 1)[0] + "…"
    return extract


def _is_admin_only_description(text: str) -> bool:
    blob = (text or "").strip()
    if not blob:
        return True
    if _ADMIN_DESCRIPTION_RE.search(blob) and len(blob) < 120:
        return True
    return False


@lru_cache(maxsize=64)
def fetch_raw_city_fact(city: str) -> str:
    """
    Богатый сырой контекст для LLM: Wikipedia lead, топ POI, Wikidata description.
    """
    center: CityCenter | None = resolve_city_center(city)
    if center is None:
        return f"Город: {city.strip()}"

    label = center.city.strip() or city.strip()
    parts: list[str] = [f"Город: {label}"]

    wiki_text = ""
    wikidata_id = center.wikidata_id or ""
    if wikidata_id:
        entity = _fetch_entity(wikidata_id)
        if entity is not None:
            for site in ("ruwiki", "enwiki"):
                title = _sitelink_title(entity, site)
                if not title:
                    continue
                lang = "ru" if site.startswith("ru") else "en"
                wiki_text = fetch_wikipedia_extract(
                    title=title,
                    lang=lang,
                    max_chars=1800,
                )
                if not wiki_text:
                    wiki_text = fetch_wikipedia_lead(title=title, lang=lang)
                if wiki_text:
                    break

        landmarks = fetch_top_landmark_names(wikidata_id, limit=5)
        if landmarks:
            parts.append("Известные места (Wikidata): " + ", ".join(landmarks))

        description = fetch_wikidata_description(wikidata_id, lang="ru")
        if not description:
            description = fetch_wikidata_description(wikidata_id, lang="en")
        if description and not _is_admin_only_description(description):
            parts.append(f"Wikidata: {description}")

    if wiki_text:
        parts.insert(1, f"Wikipedia: {wiki_text}")
    elif center.display_name:
        parts.append(f"Регион: {center.display_name.strip()}")

    return "\n".join(parts)
