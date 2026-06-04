"""Проверка и очистка раздела «Лайфхаки» (без списков музеев/ресторанов)."""

from __future__ import annotations

import re

_LIFEHACKS_MAX_CHARS = 1200

_LLM_META = re.compile(
    r"|".join(
        (
            r"\bOops\b",
            r"Let me\b",
            r"I've now filled",
            r"I’ve now filled",
            r"Final output",
            r"required JSON",
            r"```json",
            r"filled in the data",
            r"Let me know if",
            r"complete programme",
            r"complete program",
            r"Here.s the complete",
            r"properly, with:",
            r"refinements!",
        )
    ),
    re.IGNORECASE,
)

_SECTION_MARKERS = re.compile(
    r"(?im)^#{1,3}\s*(Events|Dining|Lifehacks?|Мероприятия|Питание|Лайфхак)\s*$"
)

_LIFEHACKS_START = re.compile(
    r"(?im)(?:^#{1,3}\s*Lifehacks?\s*$|^#{1,3}\s*Лайфхак|^\*\*Transport tips\*\*)"
)


def is_garbage_lifehacks(text: str) -> bool:
    """Список музеев/ресторанов, meta-текст LLM или обломок JSON."""
    t = (text or "").strip()
    if len(t) < 25:
        return True
    head = t[:32]
    if head.startswith(":[]") or head.startswith(":{") or re.match(r"^[\s:\[\]{}]+", head):
        return True
    if _LLM_META.search(t):
        return True
    if _SECTION_MARKERS.search(t):
        events_hits = len(re.findall(r"(?im)^#{1,3}\s*Events", t))
        dining_hits = len(re.findall(r"(?im)^#{1,3}\s*Dining", t))
        if events_hits or dining_hits:
            return True
    if re.search(r"(?im)^#{1,3}\s*Events", t) and re.search(r"(?im)^#{1,3}\s*Dining", t):
        return True
    if "tripadvisor" in t.lower() and len(re.findall(r"https?://", t, flags=re.I)) >= 4:
        return True
    if len(t) > _LIFEHACKS_MAX_CHARS:
        return True
    if len(re.findall(r"https?://", t, flags=re.I)) > 3:
        return True
    return False


def extract_lifehacks_block(text: str) -> str:
    """Вырезает подраздел Lifehacks из «простыни» LLM, если он там есть."""
    if not text:
        return ""
    match = _LIFEHACKS_START.search(text)
    if not match:
        return ""
    chunk = text[match.start() :]
    tail = re.search(
        r"(?is)(I've now filled|I’ve now filled|Final output|```json|Let me know if you|"
        r"The content uses only facts)",
        chunk,
    )
    if tail:
        chunk = chunk[: tail.start()]
    return chunk.strip()


def build_default_lifehacks(
    *,
    city: str,
    walking_area: str = "",
    search_context: str = "",
) -> str:
    """Короткие советы без веб-поиска."""
    area = (walking_area or "исторический центр").strip()
    lines = [
        f"Маршрут на день в {city}: утро — музей → обед в 10–15 мин пешком → "
        f"второй объект в районе {area}.",
        "Закладывайте 1,5–2 ч на музей и 1–1,5 ч на обед; вечером — прогулка рядом с последней точкой.",
        "Бронируйте столик на ужин заранее в популярных местах из раздела «Питание».",
        "Удобная обувь: в центре много пеших переходов между музеями и кафе.",
    ]
    if search_context and "пеш" in search_context.lower():
        lines.append("По предпочтениям: в приоритете пешие связки, такси — на дальние точки.")
    elif search_context and "такси" in search_context.lower():
        lines.append("По предпочтениям: между районами удобнее такси (Яндекс Go).")
    return "\n".join(f"- {line}" for line in lines)


def clean_lifehacks_display(
    text: str,
    *,
    city: str = "",
    walking_area: str = "",
    search_context: str = "",
    max_chars: int = _LIFEHACKS_MAX_CHARS,
) -> str:
    """Оставляет только советы; иначе — шаблон по умолчанию."""
    raw = (text or "").strip()
    if not raw:
        return build_default_lifehacks(
            city=city, walking_area=walking_area, search_context=search_context
        )

    candidate = raw
    if is_garbage_lifehacks(raw):
        extracted = extract_lifehacks_block(raw)
        if extracted and not is_garbage_lifehacks(extracted):
            candidate = extracted
        else:
            return build_default_lifehacks(
                city=city, walking_area=walking_area, search_context=search_context
            )

    out_lines: list[str] = []
    for line in candidate.splitlines():
        row = line.strip()
        if not row:
            if out_lines and out_lines[-1] != "":
                out_lines.append("")
            continue
        if _LLM_META.search(row):
            break
        if re.match(r"(?im)^#{1,3}\s*(Events|Dining)\b", row):
            break
        if row.startswith("```"):
            break
        if len(row) > 400:
            row = row[:400].rsplit(" ", 1)[0] + "…"
        out_lines.append(row)

    blob = "\n".join(out_lines).strip()
    blob = re.sub(r"(?im)^#{1,3}\s*Lifehacks?\s*$", "", blob).strip()
    while "\n\n\n" in blob:
        blob = blob.replace("\n\n\n", "\n\n")
    if not blob or is_garbage_lifehacks(blob):
        return build_default_lifehacks(
            city=city, walking_area=walking_area, search_context=search_context
        )
    if len(blob) > max_chars:
        blob = blob[:max_chars].rsplit("\n", 1)[0] + "\n…"
    return blob
