"""Парсинг дат поездки из свободного текста CLI."""

from __future__ import annotations

import re
from datetime import date, datetime

from models.tickets import ParsedTripDates

_MONTHS: dict[str, int] = {
    "январ": 1,
    "феврал": 2,
    "март": 3,
    "апрел": 4,
    "ма": 5,
    "июн": 6,
    "июл": 7,
    "август": 8,
    "сентябр": 9,
    "октябр": 10,
    "ноябр": 11,
    "декабр": 12,
}


def _parse_iso(text: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_russian_day_month(text: str, default_year: int | None) -> date | None:
    m = re.search(
        r"(\d{1,2})\s*"
        r"("
        r"январ[ья]?|феврал[ья]?|март[а]?|апрел[ья]?|ма[йя]?|июн[ья]?|"
        r"июл[ья]?|август[а]?|сентябр[ья]?|октябр[ья]?|ноябр[ья]?|декабр[ья]?"
        r")"
        r"(?:\s+(\d{4}))?",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    day = int(m.group(1))
    month_key = m.group(2).lower()
    month = next((num for key, num in _MONTHS.items() if month_key.startswith(key)), None)
    if month is None:
        return None
    year = int(m.group(3)) if m.group(3) else default_year
    if year is None:
        year = date.today().year
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _extract_year(text: str) -> int | None:
    m = re.search(r"(20\d{2})", text)
    return int(m.group(1)) if m else None


def _split_range(text: str) -> tuple[str, str] | None:
    normalized = text.replace("–", "-").replace("—", "-").replace("−", "-").strip()
    iso_pair = re.match(
        r"^(\d{4}-\d{2}-\d{2})\s*-\s*(\d{4}-\d{2}-\d{2})$",
        normalized,
    )
    if iso_pair:
        return iso_pair.group(1), iso_pair.group(2)
    dot_pair = re.match(
        r"^(\d{1,2}\.\d{1,2}\.\d{4})\s*-\s*(\d{1,2}\.\d{1,2}\.\d{4})$",
        normalized,
    )
    if dot_pair:
        return dot_pair.group(1), dot_pair.group(2)
    parts = re.split(r"\s*-\s*", normalized, maxsplit=1)
    if len(parts) == 2 and parts[0].strip() and parts[1].strip():
        return parts[0].strip(), parts[1].strip()
    return None


def _parse_day_in_shared_month(
    day_text: str,
    month_anchor: str,
    year_hint: int | None,
) -> date | None:
    """«15» + якорь «18 июля 2026» → 15 июля 2026."""
    m = re.search(
        r"("
        r"январ[ья]?|феврал[ья]?|март[а]?|апрел[ья]?|ма[йя]?|июн[ья]?|"
        r"июл[ья]?|август[а]?|сентябр[ья]?|октябр[ья]?|ноябр[ья]?|декабр[ья]?"
        r")(?:\s+(\d{4}))?",
        month_anchor,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    year = year_hint or (int(m.group(2)) if m.group(2) else None)
    combined = f"{day_text.strip()} {m.group(1)}"
    if year:
        combined += f" {year}"
    return _parse_russian_day_month(combined, year)


def parse_trip_dates(dates_raw: str) -> ParsedTripDates:
    """
    Извлекает дату вылета и возврата из строки вроде «15-18 июля 2026».
    """
    raw = dates_raw.strip()
    if not raw:
        return ParsedTripDates(raw=raw, parse_status="failed")

    year_hint = _extract_year(raw)
    range_parts = _split_range(raw)

    if range_parts:
        left, right = range_parts
        year = year_hint or _extract_year(right) or _extract_year(left)
        dep = _parse_iso(left) or _parse_russian_day_month(left, year)
        ret = _parse_iso(right) or _parse_russian_day_month(right, year)
        if not dep and re.fullmatch(r"\d{1,2}", left.strip()):
            dep = _parse_day_in_shared_month(left, right, year)
        if dep and ret:
            return ParsedTripDates(
                departure=dep,
                return_date=ret,
                raw=raw,
                parse_status="ok",
            )
        if dep and not ret:
            ret = _parse_russian_day_month(right, dep.year)
            if ret:
                return ParsedTripDates(
                    departure=dep,
                    return_date=ret,
                    raw=raw,
                    parse_status="ok",
                )
        if dep:
            return ParsedTripDates(
                departure=dep,
                return_date=None,
                raw=raw,
                parse_status="partial",
            )

    single = _parse_iso(raw) or _parse_russian_day_month(raw, year_hint)
    if single:
        return ParsedTripDates(
            departure=single,
            return_date=None,
            raw=raw,
            parse_status="partial",
        )

    return ParsedTripDates(raw=raw, parse_status="failed")
