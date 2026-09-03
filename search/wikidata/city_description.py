"""Туристический контекст о городе: Wikipedia, Wikidata, топ POI."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from search.osm.nominatim import CityCenter, resolve_city_center
from search.wikidata.places import fetch_top_landmark_names

_USER_AGENT = "tourist-assistant/1.0 (city-fact; local dev)"
_WIKI_LEAD_MAX = 900
# Wikipedia `exchars` на практике режет ~1200 символов и всегда ставит «...».
# POI-модалка: +~200 символов ≈ 70–80px. Блок «О городе» — отдельный, более длинный лимит.
WIKI_SNIPPET_MAX_CHARS = 1400
CITY_WIKI_MAX_CHARS = 2800
WIKIPEDIA_READ_MORE_LABEL = "Читать далее в Wikipedia"
_TRAILING_ELLIPSIS_RE = re.compile(r"([.]{3}|…)+\s*$")
_WIKIPEDIA_URL_LINE_RE = re.compile(r"(?m)^Wikipedia-URL:\s*(\S+)\s*$")
_READ_MORE_MARKDOWN_RE = re.compile(
    rf"\n*\s*\[{re.escape(WIKIPEDIA_READ_MORE_LABEL)}\]\([^)]+\)\s*$"
)
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


_WIKI_SECTION_RE = re.compile(r"^=+\s*.+?\s*=+$", re.M)


def normalize_wiki_title(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").strip().casefold().replace("ё", "е"))


def wikipedia_page_url(*, title: str, lang: str = "ru") -> str:
    encoded = quote((title or "").replace(" ", "_"), safe="")
    return f"https://{lang}.wikipedia.org/wiki/{encoded}"


def extract_wikipedia_url(raw: str) -> str:
    match = _WIKIPEDIA_URL_LINE_RE.search(raw or "")
    return (match.group(1) if match else "").strip()


def strip_wikipedia_meta(raw: str) -> str:
    """Убирает служебные Wikipedia-URL/Title из сырого контекста (не для LLM)."""
    return _WIKIPEDIA_URL_LINE_RE.sub("", raw or "").strip()


def strip_wikipedia_read_more(text: str) -> str:
    """Убирает markdown-ссылку «Читать далее» и хвостовое троеточие превью."""
    blob = _READ_MORE_MARKDOWN_RE.sub("", text or "").strip()
    return _TRAILING_ELLIPSIS_RE.sub("", blob).rstrip(" \t").strip()


def with_continuation_ellipsis(text: str) -> str:
    """Ставит « …» после законченного предложения — не посреди фразы."""
    blob = _TRAILING_ELLIPSIS_RE.sub("", (text or "").strip()).strip()
    if not blob:
        return ""
    if blob.endswith((".", "!", "?")):
        return blob + " …"
    return blob + "…"


def append_wikipedia_read_more(
    text: str,
    *,
    title: str = "",
    lang: str = "ru",
    url: str = "",
    preview_ellipsis: bool = False,
) -> str:
    blob = (text or "").strip()
    link_url = (url or "").strip() or (
        wikipedia_page_url(title=title, lang=lang) if title else ""
    )
    if not blob or not link_url:
        return blob
    if WIKIPEDIA_READ_MORE_LABEL in blob or link_url in blob:
        return blob
    if preview_ellipsis:
        blob = with_continuation_ellipsis(blob)
    return f"{blob}\n\n[{WIKIPEDIA_READ_MORE_LABEL}]({link_url})"


@dataclass(frozen=True)
class WikipediaSnippet:
    text: str
    title: str = ""
    lang: str = "ru"

    @property
    def url(self) -> str:
        if not self.title:
            return ""
        return wikipedia_page_url(title=self.title, lang=self.lang)

    def formatted(self, *, read_more: bool = True) -> str:
        blob = (self.text or "").strip()
        if read_more:
            return append_wikipedia_read_more(
                blob, title=self.title, lang=self.lang
            )
        return blob


def clean_wikipedia_plain(text: str) -> str:
    """Убирает заголовки разделов Wikipedia (== … ==) и лишние пробелы."""
    blob = _WIKI_SECTION_RE.sub("", (text or "").strip())
    blob = re.sub(r"\n{3,}", "\n\n", blob)
    return re.sub(r" +", " ", blob).strip()


_INITIAL_TAIL_RE = re.compile(r"(?:^|[^\w])[A-ZА-ЯЁ]\.$")
_ABBREV_WORD_TAIL_RE = re.compile(
    r"(?i)\b(?:г|ул|пр|пл|им|тыс|млн|км|св|др|обл|ст)\.$"
)
_HANGING_TAIL_RE = re.compile(
    r"(?i)(?:^|[,;\s])(?:и|или|а также|в том числе|имени|им\.?)$"
)
_PROTECT_INITIAL_RE = re.compile(r"\b([A-ZА-ЯЁ])\.")
_PROTECT_ABBREV_RE = re.compile(r"\b(г|ул|пр|пл|им|тыс|млн|км|св|др)\.", re.I)


def looks_truncated_tail(text: str) -> bool:
    """Хвост обрезан: инициал («М.»), сокращение, запятая, «имени», нет .!?"""
    blob = (text or "").rstrip()
    if not blob:
        return True
    if blob[-1] in ",;:":
        return True
    if _INITIAL_TAIL_RE.search(blob) or _ABBREV_WORD_TAIL_RE.search(blob):
        return True
    hanging = blob[:-1].rstrip() if blob[-1] in ".!?" else blob
    if _HANGING_TAIL_RE.search(hanging):
        return True
    return blob[-1] not in ".!?"


def split_real_sentences(text: str) -> list[str]:
    """Дробит по .!? , не рвя инициалы (М. Шкетан) и сокращения (г., ул., им.)."""
    marker = "\x00"

    def _protect_initial(match: re.Match[str]) -> str:
        return match.group(1) + marker

    protected = _PROTECT_INITIAL_RE.sub(_protect_initial, text or "")
    protected = _PROTECT_ABBREV_RE.sub(_protect_initial, protected)
    parts = re.split(r"(?<=[.!?])\s+", protected)
    return [p.replace(marker, ".").strip() for p in parts if p.strip()]


def drop_incomplete_sentence(text: str) -> str:
    """Убирает оборванный хвост: незаконченная фраза, инициал, обрезанный пункт списка."""
    blob = _TRAILING_ELLIPSIS_RE.sub("", (text or "").strip()).strip()
    if not blob:
        return ""
    if not looks_truncated_tail(blob):
        return blob
    sentences = split_real_sentences(blob)
    if not sentences:
        return blob
    last = sentences[-1]
    if looks_truncated_tail(last) and "," in last:
        head = last.rsplit(",", 1)[0].strip()
        if head and len(head) >= 20:
            sentences[-1] = head
            return " ".join(sentences).strip()
    if looks_truncated_tail(last) and len(sentences) > 1:
        return " ".join(sentences[:-1]).strip()
    if "," in blob:
        head = blob.rsplit(",", 1)[0].strip()
        if head:
            return head
    return blob


def trim_to_semantic_boundary(
    text: str,
    max_chars: int,
    *,
    ellipsis: bool = False,
) -> str:
    """
    Обрезка по абзацу или предложению, не посреди слова и не на полуфразе.

    - Сначала окно max_chars по границе слова.
    - Если в окне есть абзац достаточной длины — берём его.
    - Иначе — последнее законченное предложение.
    - ellipsis=True: после обрезки ставит « …» (для превью Wikipedia).
    """
    blob = _TRAILING_ELLIPSIS_RE.sub("", (text or "").strip()).strip()
    if not blob:
        return ""
    original_len = len(blob)
    if original_len > max_chars:
        window = blob[:max_chars]
        para = window.rsplit("\n\n", 1)[0].strip()
        if para and len(para) >= min(400, max_chars // 2):
            window = para
        else:
            window = window.rsplit(" ", 1)[0].strip()
        blob = window
    complete = drop_incomplete_sentence(blob)
    if complete and complete[-1:] in ".!?":
        blob = complete
    elif complete:
        blob = complete
    truncated = original_len > len(blob)
    if ellipsis and truncated:
        blob = with_continuation_ellipsis(blob)
    return blob


def trim_wikipedia_text(text: str, max_chars: int, *, ellipsis: bool = True) -> str:
    blob = clean_wikipedia_plain(text)
    return trim_to_semantic_boundary(blob, max_chars, ellipsis=ellipsis)


def fetch_wikipedia_lead(*, title: str, lang: str = "ru", max_chars: int | None = None) -> str:
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
    cap = max_chars if max_chars is not None else _WIKI_LEAD_MAX
    return trim_wikipedia_text(extract, cap, ellipsis=cap < len(extract))


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


def city_wikipedia_titles(city: str) -> set[str]:
    """Названия статей города — их нельзя подставлять как справку по POI."""
    titles = {normalize_wiki_title(city)}
    center = resolve_city_center(city)
    if center is not None:
        if center.city:
            titles.add(normalize_wiki_title(center.city))
        wikidata_id = (center.wikidata_id or "").strip()
        if wikidata_id:
            entity = _fetch_entity(wikidata_id)
            if entity is not None:
                for site in ("ruwiki", "enwiki"):
                    title = _sitelink_title(entity, site)
                    if title:
                        titles.add(normalize_wiki_title(title))
    return titles


def fetch_wikipedia_for_wikidata(
    wikidata_id: str,
    *,
    lang: str = "ru",
    max_chars: int = 1400,
) -> str:
    """Lead или extract статьи, привязанной к Wikidata QID."""
    qid = (wikidata_id or "").strip()
    if not qid:
        return ""
    entity = _fetch_entity(qid)
    if entity is None:
        return ""
    for site in ("ruwiki", "enwiki"):
        title = _sitelink_title(entity, site)
        if not title:
            continue
        page_lang = "ru" if site.startswith("ru") else "en"
        lead = fetch_wikipedia_lead(title=title, lang=page_lang, max_chars=max_chars)
        if lead and len(lead) >= 40:
            return lead
        extract = fetch_wikipedia_extract(
            title=title,
            lang=page_lang,
            max_chars=max_chars,
            ellipsis=False,
        )
        if extract and len(extract) >= 40:
            return extract
    desc = fetch_wikidata_description(qid, lang=lang)
    return desc if desc and len(desc) >= 40 else ""


def fetch_wikipedia_poi_text(
    *,
    title: str,
    lang: str = "ru",
    max_chars: int = WIKI_SNIPPET_MAX_CHARS,
) -> WikipediaSnippet:
    """Фрагмент статьи для справки по месту: полный intro, при нехватке — тело статьи."""
    intro = fetch_wikipedia_extract(
        title=title,
        lang=lang,
        max_chars=max_chars,
        ellipsis=False,
        intro_only=True,
    )
    text = intro
    # Wikipedia `exchars` давал ~1200 с «…». Если intro короче — добираем тело статьи.
    if len(intro) < min(max_chars, 1200):
        full = fetch_wikipedia_extract(
            title=title,
            lang=lang,
            max_chars=max_chars,
            ellipsis=False,
            intro_only=False,
        )
        if len(full) > len(intro):
            text = full
    if len(text) < 40:
        text = fetch_wikipedia_lead(title=title, lang=lang, max_chars=max_chars)
    return WikipediaSnippet(text=text, title=title, lang=lang)


def fetch_wikipedia_poi_for_wikidata(
    wikidata_id: str,
    *,
    lang: str = "ru",
    max_chars: int = WIKI_SNIPPET_MAX_CHARS,
) -> WikipediaSnippet:
    """Extract статьи по Wikidata QID для справки по POI."""
    empty = WikipediaSnippet(text="", title="", lang=lang)
    qid = (wikidata_id or "").strip()
    if not qid:
        return empty
    entity = _fetch_entity(qid)
    if entity is None:
        return empty
    for site in ("ruwiki", "enwiki"):
        title = _sitelink_title(entity, site)
        if not title:
            continue
        page_lang = "ru" if site.startswith("ru") else "en"
        snippet = fetch_wikipedia_poi_text(
            title=title,
            lang=page_lang,
            max_chars=max_chars,
        )
        if snippet.text and len(snippet.text) >= 40:
            return snippet
    desc = fetch_wikidata_description(qid, lang=lang)
    if desc and len(desc) >= 40:
        return WikipediaSnippet(text=desc, title="", lang=lang)
    return empty


def fetch_wikipedia_extract(
    *,
    title: str,
    lang: str = "ru",
    max_chars: int = WIKI_SNIPPET_MAX_CHARS,
    ellipsis: bool = True,
    intro_only: bool = False,
) -> str:
    """
    Фрагмент статьи Wikipedia (plain text).

    Без `exchars`: Wikipedia иначе обрезает ~1200 символов и ставит «...».
    `intro_only=True` — полный lead-раздел (для города, без гигантской статьи).
    """
    title = (title or "").strip()
    if not title:
        return ""
    extra = "&exintro=1" if intro_only else ""
    url = (
        f"https://{lang}.wikipedia.org/w/api.php?"
        "action=query&format=json&utf8=1&explaintext=1"
        f"&prop=extracts{extra}&titles={quote(title)}"
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
    extract = clean_wikipedia_plain(extract)
    return trim_wikipedia_text(extract, max_chars, ellipsis=ellipsis)


def fetch_wikipedia_city_text(
    *,
    title: str,
    lang: str = "ru",
    max_chars: int = CITY_WIKI_MAX_CHARS,
) -> str:
    """Фрагмент статьи о городе: полный intro, при нехватке — тело до max_chars."""
    intro = fetch_wikipedia_extract(
        title=title,
        lang=lang,
        max_chars=max_chars,
        ellipsis=False,
        intro_only=True,
    )
    if len(intro) >= max_chars:
        return intro
    full = fetch_wikipedia_extract(
        title=title,
        lang=lang,
        max_chars=max_chars,
        ellipsis=False,
        intro_only=False,
    )
    return full if len(full) > len(intro) else intro


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
    wiki_title = ""
    wiki_lang = "ru"
    wikidata_id = center.wikidata_id or ""
    if wikidata_id:
        entity = _fetch_entity(wikidata_id)
        if entity is not None:
            for site in ("ruwiki", "enwiki"):
                title = _sitelink_title(entity, site)
                if not title:
                    continue
                lang = "ru" if site.startswith("ru") else "en"
                wiki_text = fetch_wikipedia_city_text(
                    title=title,
                    lang=lang,
                    max_chars=CITY_WIKI_MAX_CHARS,
                )
                if not wiki_text:
                    wiki_text = fetch_wikipedia_lead(
                        title=title,
                        lang=lang,
                        max_chars=CITY_WIKI_MAX_CHARS,
                    )
                if wiki_text:
                    wiki_title = title
                    wiki_lang = lang
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
        insert_at = 1
        parts.insert(insert_at, f"Wikipedia: {wiki_text}")
        if wiki_title:
            parts.insert(
                insert_at + 1,
                f"Wikipedia-URL: {wikipedia_page_url(title=wiki_title, lang=wiki_lang)}",
            )
    elif center.display_name:
        parts.append(f"Регион: {center.display_name.strip()}")

    return "\n".join(parts)
