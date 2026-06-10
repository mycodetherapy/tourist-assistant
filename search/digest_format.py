"""Очистка сниппетов и компактный digest для мероприятий (без мусора с сайтов)."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

_SNIPPET_MAX = 220
_EVENTS_DIGEST_MAX = 8

_AGGREGATOR_URL = re.compile(
    r"|".join(
        (
            r"afisha\.ru/[^/]+/(events|exhibitions|museum)/?$",
            r"culture\.ru/afisha/[^/]+/vistavki/?",
            r"idemvmuzei\.ru/exhibition/city/",
            r"syktyvkar\.kassir\.ru/?$",
            r"afisha\.yandex\.ru/[^/?]+/?$",
            r"personalguide\.ru/[^/]+/museum/?$",
        )
    ),
    re.IGNORECASE,
)

_JUNK_LINE = re.compile(
    r"|".join(
        (
            r"\{\{",
            r"\}\}",
            r"formatNumber",
            r"to_display_name",
            r"Размер\s+шрифта",
            r"Черно-белые",
            r"Загрузите в App Store",
            r"Top\.Mail\.Ru",
            r"cookie",
            r"Lang icon",
            r"^\s*\|\s*\|",  # markdown table row
            r"^---\s*$",
            r"^\s*\+\s*$",
            r"^\s*−\s*$",
            r"Отправляю\.\.\.",
            r"Заказать экскурсию можно",
            r"Загрузка погоды",
            r"### Ссылки",
            r"Календарь",
            r"Panorama",
            r"Search nearby",
            r"Directions",
            r"Service organizations",
            r"Otdeleniye pochtovoy",
            r"^\s*\|\s*«\s*\|",
            r"^\s*\|\s*Пн\s*\|",
            r"Iyun\s+\d{4}",
            r"Июнь\s+\d{4}",
        )
    ),
    re.IGNORECASE,
)

_MUSEUM_URL_HINT = re.compile(
    r"museum|музей|gallery|галере|ngrk|hermitage|tretyakov|institutes/\d+",
    re.IGNORECASE,
)

_LINE_WITH_URL = re.compile(
    r"^(\d+\.\s*)(.+?)\s*[—–-]\s*(https?://[^\s\)\],]+)\s*(.*)$",
    re.DOTALL,
)

_MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(https?://")


def _link_label(title: str, url: str) -> str:
    """Короткая подпись для Markdown-ссылки."""
    t = re.sub(r"\s+", " ", (title or "").strip())
    if len(t) > 72:
        t = t[:72].rsplit(" ", 1)[0] + "…"
    host = urlparse(url).netloc.replace("www.", "")
    if len(t) < 5 or t.lower() in ("выставки", "купить билеты", "мероприятия"):
        return host or "ссылка"
    return t


def _strip_duplicate_lead(rest: str, title: str) -> str:
    """Убирает повтор заголовка в хвосте строки после URL."""
    rest = (rest or "").strip().lstrip("., ")
    if not rest:
        return ""
    head = title[:40].lower()
    if rest.lower().startswith(head):
        cut = rest[len(title) :].lstrip(" .,—–-")
        return cut.strip()
    return rest


def format_event_entry(
    index: int,
    title: str,
    url: str,
    snippet: str = "",
) -> str:
    """Одна строка мероприятия: кликабельная Markdown-ссылка."""
    label = _link_label(title, url)
    line = f"{index}. [{label}]({url})"
    snip = sanitize_snippet(snippet)
    if snip:
        line += f" — {snip}"
    return line


def linkify_event_line(line: str) -> str:
    """Превращает «название — https://…» в «[название](https://…)»."""
    raw = line.strip()
    if not raw or _MARKDOWN_LINK.search(raw):
        return raw
    match = _LINE_WITH_URL.match(raw)
    if match:
        prefix, title, url, rest = match.groups()
        url = url.rstrip(".,;)")
        rest = _strip_duplicate_lead(rest, title)
        rest = sanitize_snippet(rest) if rest else ""
        label = _link_label(title, url)
        out = f"{prefix}[{label}]({url})"
        if rest:
            out += f" — {rest}"
        return out
    return _linkify_bare_urls(raw)


def _linkify_bare_urls(line: str) -> str:
    """Заменяет голые URL на [host](url), если ещё не в Markdown."""

    def repl(match: re.Match[str]) -> str:
        url = match.group(0).rstrip(".,;)")
        host = urlparse(url).netloc.replace("www.", "") or "ссылка"
        return f"[{host}]({url})"

    return re.sub(r"https?://[^\s\)\],]+", repl, line)


def sanitize_snippet(text: str, *, max_len: int = _SNIPPET_MAX) -> str:
    """Убирает UI/шаблоны сайтов, сжимает до короткой подписи."""
    if not text:
        return ""
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        raw = line.strip()
        if not raw or _JUNK_LINE.search(raw):
            continue
        if len(raw) > 400 and not cleaned_lines:
            raw = raw[:400]
        cleaned_lines.append(raw)
    blob = " ".join(cleaned_lines)
    blob = re.sub(r"\s+", " ", blob).strip()
    blob = re.sub(r"\[\.\.\.\]", "…", blob)
    if len(blob) > max_len:
        cut = blob[:max_len].rsplit(" ", 1)[0]
        blob = (cut or blob[:max_len]).rstrip(".,;") + "…"
    return blob


def is_aggregator_events_url(url: str) -> bool:
    """Городские ленты афиши — не конкретный музей/выставка."""
    if not url:
        return True
    return bool(_AGGREGATOR_URL.search(url))


def _events_url_score(url: str) -> int:
    if not url or is_aggregator_events_url(url):
        return -50
    low = url.lower()
    score = 0
    if _MUSEUM_URL_HINT.search(low):
        score += 15
    if re.search(r"culture\.ru/(events/\d+|institutes/)", low):
        score += 12
    if re.search(r"/(exhibition|exhibitions|cat=|page_id=)", low):
        score += 8
    if "afisha.ru" in low and not is_aggregator_events_url(url):
        score += 3
    return score


def rank_events_results(
    results: list[dict[str, str | None]],
) -> list[dict[str, str | None]]:
    """Сначала прямые страницы музеев, агрегаторы — в конец или отсечение."""

    def sort_key(item: dict[str, str | None]) -> tuple[int, int]:
        url = item.get("url") or ""
        snippet = item.get("snippet") or ""
        score = _events_url_score(url)
        if _JUNK_LINE.search(snippet[:500]):
            score -= 30
        return (score, -len(snippet))

    ranked = sorted(results, key=sort_key, reverse=True)
    good: list[dict[str, str | None]] = []
    for item in ranked:
        url = item.get("url") or ""
        if is_aggregator_events_url(url) and len(good) >= 3:
            continue
        snip = sanitize_snippet(str(item.get("snippet") or ""))
        if not snip and is_aggregator_events_url(url):
            continue
        good.append({**item, "snippet": snip or item.get("snippet")})
        if len(good) >= _EVENTS_DIGEST_MAX:
            break
    return good


def format_events_digest(results: list[dict[str, str | None]]) -> str:
    """Короткий digest для LLM: 5–8 объектов, без простыней с сайтов."""
    picked = rank_events_results(results)
    if not picked:
        return "Конкретных мероприятий в поиске мало — укажите 3–5 музеев с официальных сайтов."
    lines: list[str] = []
    for index, item in enumerate(picked, start=1):
        title = (item.get("title") or "Мероприятие").strip()
        title = re.sub(r"\s+", " ", title)[:120]
        url = (item.get("url") or "").strip()
        snippet = sanitize_snippet(str(item.get("snippet") or ""))
        if url:
            lines.append(format_event_entry(index, title, url, snippet))
        else:
            lines.append(f"{index}. {title}" + (f" — {snippet}" if snippet else ""))
    return "\n".join(lines)
