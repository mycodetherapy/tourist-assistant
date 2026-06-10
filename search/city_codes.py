"""Сопоставление названий городов с IATA (РФ и популярные зарубежные направления)."""

from __future__ import annotations

import re

# Ключ — нормализованное русское название; значение — IATA аэропорта (часто главный).
_CITY_IATA: dict[str, str] = {
    "москва": "MOW",
    "санкт-петербург": "LED",
    "петербург": "LED",
    "питер": "LED",
    "новосибирск": "OVB",
    "екатеринбург": "SVX",
    "казань": "KZN",
    "нижний новгород": "GOJ",
    "самара": "KUF",
    "омск": "OMS",
    "челябинск": "CEK",
    "ростов-на-дону": "ROV",
    "уфа": "UFA",
    "красноярск": "KJA",
    "пермь": "PEE",
    "волгоград": "VOG",
    "воронеж": "VOZ",
    "саратов": "GSV",
    "краснодар": "KRR",
    "тюмень": "TJM",
    "ижевск": "IJK",
    "барнаул": "BAX",
    "ульяновск": "ULV",
    "иркутск": "IKT",
    "хабаровск": "KHV",
    "владивосток": "VVO",
    "ярославль": "IAR",
    "махачкала": "MCX",
    "томск": "TOF",
    "оренбург": "REN",
    "кемерово": "KEJ",
    "новокузнецк": "NOZ",
    "рязань": "RZN",
    "астрахань": "ASF",
    "пенза": "PEZ",
    "липецк": "LPK",
    "калининград": "KGD",
    "тверь": "KLD",
    "курск": "URS",
    "сочи": "AER",
    "ставрополь": "STW",
    "белгород": "EGO",
    "сыктывкар": "SCW",
    "мурманск": "MMK",
    "архангельск": "ARH",
    "сургут": "SGC",
    "чита": "HTA",
    "якутск": "YKS",
    "муром": "UUA",
    "владикавказ": "OGZ",
    "грозный": "GRV",
    "нальчик": "NAL",
    "магадан": "GDX",
    "петропавловск-камчатский": "PKC",
    "южно-сахалинск": "UUS",
    # Зарубежные направления (IATA city/metro для Aviasales API и deep links)
    "стамбул": "IST",
    "istanbul": "IST",
    "анталья": "AYT",
    "antalya": "AYT",
    "дубай": "DXB",
    "dubai": "DXB",
    "бангкок": "BKK",
    "bangkok": "BKK",
    "пхукет": "HKT",
    "phuket": "HKT",
    "париж": "PAR",
    "paris": "PAR",
    "рим": "ROM",
    "rome": "ROM",
    "барселона": "BCN",
    "barcelona": "BCN",
    "лондон": "LON",
    "london": "LON",
    "прага": "PRG",
    "prague": "PRG",
    "берлин": "BER",
    "berlin": "BER",
    "белград": "BEG",
    "belgrade": "BEG",
    "тбилиси": "TBS",
    "tbilisi": "TBS",
    "ереван": "EVN",
    "yerevan": "EVN",
    "баку": "BAK",
    "baku": "BAK",
    "минск": "MSQ",
    "minsk": "MSQ",
    "астана": "NQZ",
    "astana": "NQZ",
    "алматы": "ALA",
    "almaty": "ALA",
    "ташкент": "TAS",
    "tashkent": "TAS",
    "бишкек": "FRU",
    "bishkek": "FRU",
    "душанбе": "DYU",
    "dushanbe": "DYU",
    "вена": "VIE",
    "vienna": "VIE",
    "амстердам": "AMS",
    "amsterdam": "AMS",
    "афины": "ATH",
    "athens": "ATH",
    "милан": "MIL",
    "milan": "MIL",
    "будапешт": "BUD",
    "budapest": "BUD",
    "варшава": "WAW",
    "warsaw": "WAW",
    "хельсинки": "HEL",
    "helsinki": "HEL",
    "стокгольм": "STO",
    "stockholm": "STO",
    "тель-авив": "TLV",
    "tel aviv": "TLV",
    "каир": "CAI",
    "cairo": "CAI",
    "хургада": "HRG",
    "hurghada": "HRG",
    "шарм-эль-шейх": "SSH",
    "шарм эль шейх": "SSH",
    "sharm el sheikh": "SSH",
    "бали": "DPS",
    "bali": "DPS",
    "денпасар": "DPS",
    "пекин": "BJS",
    "beijing": "BJS",
    "шанхай": "SHA",
    "shanghai": "SHA",
    "сеул": "SEL",
    "seoul": "SEL",
    "токио": "TYO",
    "tokyo": "TYO",
    "нью-йорк": "NYC",
    "new york": "NYC",
    "майами": "MIA",
    "miami": "MIA",
    "лос-анджелес": "LAX",
    "los angeles": "LAX",
}

# Зарубежные направления из _CITY_IATA (не добавляем «, Россия» в геокодинг).
_FOREIGN_CITY_KEYS: frozenset[str] = frozenset(
    k
    for k in _CITY_IATA
    if k
    in {
        "стамбул",
        "istanbul",
        "анталья",
        "antalya",
        "дубай",
        "dubai",
        "бангкок",
        "bangkok",
        "пхукет",
        "phuket",
        "париж",
        "paris",
        "рим",
        "rome",
        "барселона",
        "barcelona",
        "лондон",
        "london",
        "прага",
        "prague",
        "берлин",
        "berlin",
        "белград",
        "belgrade",
        "тбилиси",
        "tbilisi",
        "ереван",
        "yerevan",
        "баку",
        "baku",
        "минск",
        "minsk",
        "астана",
        "astana",
        "алматы",
        "almaty",
        "ташкент",
        "tashkent",
        "бишкек",
        "bishkek",
        "душанбе",
        "dushanbe",
        "вена",
        "vienna",
        "амстердам",
        "amsterdam",
        "афины",
        "athens",
        "милан",
        "milan",
        "будапешт",
        "budapest",
        "варшава",
        "warsaw",
        "хельсинки",
        "helsinki",
        "стокгольм",
        "stockholm",
        "тель-авив",
        "tel aviv",
        "каир",
        "cairo",
        "хургада",
        "hurghada",
        "шарм-эль-шейх",
        "шарм эль шейх",
        "sharm el sheikh",
        "бали",
        "bali",
        "денпасар",
        "пекин",
        "beijing",
        "шанхай",
        "shanghai",
        "сеул",
        "seoul",
        "токио",
        "tokyo",
        "нью-йорк",
        "new york",
        "майами",
        "miami",
        "лос-анджелес",
        "los angeles",
    }
)


def is_foreign_destination(city: str) -> bool:
    """Зарубежный город — геокодинг без суффикса «, Россия»."""
    key = normalize_city_name(city)
    if key in _FOREIGN_CITY_KEYS:
        return True
    return any(name in key or key in name for name in _FOREIGN_CITY_KEYS)


def geocode_place_queries(city: str) -> tuple[str, ...]:
    """Варианты запроса Nominatim/Overpass: сначала без страны, для РФ — с «Россия»."""
    cleaned = city.strip()
    if not cleaned:
        return ()
    if is_foreign_destination(cleaned):
        return (cleaned,)
    return (cleaned, f"{cleaned}, Россия")


def normalize_city_name(city: str) -> str:
    text = city.lower().strip().replace("ё", "е")
    text = re.sub(r"^г\.?\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def city_to_iata(city: str) -> str | None:
    """Возвращает IATA или None, если город не в справочнике."""
    key = normalize_city_name(city)
    if key in _CITY_IATA:
        return _CITY_IATA[key]
    for name, code in _CITY_IATA.items():
        if name in key or key in name:
            return code
    return None


def _title_city_name(normalized: str) -> str:
    def cap(part: str) -> str:
        if "-" in part:
            return "-".join(p.capitalize() for p in part.split("-"))
        return part.capitalize()

    return " ".join(cap(p) for p in normalized.split())


def domestic_iata_hubs() -> tuple[tuple[str, str, str], ...]:
    """
    Российские города из _CITY_IATA: (ключ для геокодинга, IATA, подпись).
    По одному представителю на IATA — для поиска ближайшего аэропорта.
    """
    by_iata: dict[str, str] = {}
    for key, iata in _CITY_IATA.items():
        if key in _FOREIGN_CITY_KEYS:
            continue
        prev = by_iata.get(iata)
        if prev is None or len(key) > len(prev):
            by_iata[iata] = key
    return tuple(
        (name, iata, _title_city_name(name))
        for iata, name in sorted(by_iata.items(), key=lambda row: row[1])
    )
