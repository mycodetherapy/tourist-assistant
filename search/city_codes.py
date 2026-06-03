"""Сопоставление названий городов с IATA (авиа, фаза 1)."""

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
}


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
