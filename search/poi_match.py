"""Fuzzy-match названий из веб-discovery к пулу OSM/Wikidata POI."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from models.routes import PoiPoint

_MIN_SCORE = 0.52
_STRONG_SCORE = 0.72

_STRIP_RE = re.compile(
    r"^(?:музей|театр|парк|площадь|набережная|памятник|сквер|собор|храм|"
    r"галерея|мемориал|монумент|дворец|кремль)\s+",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    text = text.lower().replace("ё", "е").strip()
    text = re.sub(r"[«»\"'()]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _tokens(text: str) -> set[str]:
    return {t for t in _normalize(text).split() if len(t) >= 3}


def name_similarity(a: str, b: str) -> float:
    na, nb = _normalize(a), _normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb or na in nb or nb in na:
        return 0.95
    ratio = SequenceMatcher(None, na, nb).ratio()
    ta, tb = _tokens(na), _tokens(nb)
    if ta and tb:
        overlap = len(ta & tb) / max(len(ta), len(tb))
        ratio = max(ratio, overlap * 0.85 + 0.1)
    return ratio


@dataclass(frozen=True)
class PoiMatch:
    discovery_name: str
    poi_id: str
    poi_name: str
    score: float


def match_names_to_pool(
    names: list[str],
    pool: list[PoiPoint],
    *,
    min_score: float = _MIN_SCORE,
) -> list[PoiMatch]:
    """Для каждого discovery-названия — лучший POI из пула."""
    if not names or not pool:
        return []
    matches: list[PoiMatch] = []
    used_poi: set[str] = set()
    for raw_name in names:
        query = _STRIP_RE.sub("", raw_name).strip() or raw_name
        best: PoiMatch | None = None
        for poi in pool:
            if poi.poi_id in used_poi:
                continue
            score = name_similarity(query, poi.name)
            if score < min_score:
                continue
            if best is None or score > best.score:
                best = PoiMatch(
                    discovery_name=raw_name,
                    poi_id=poi.poi_id,
                    poi_name=poi.name,
                    score=round(score, 3),
                )
        if best is not None:
            used_poi.add(best.poi_id)
            matches.append(best)
    return matches


def strong_match_ids(matches: list[PoiMatch]) -> set[str]:
    return {m.poi_id for m in matches if m.score >= _STRONG_SCORE}
