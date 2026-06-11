"""Сопоставление URL → провайдер affiliate."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from search.affiliate.config import (
    affiliate_aviasales_enabled,
    affiliate_booking_enabled,
    affiliate_tutu_bus_enabled,
    affiliate_tutu_train_enabled,
)


@dataclass(frozen=True)
class AffiliateProvider:
    key: str
    label: str


PROVIDER_AVIASALES = AffiliateProvider("aviasales", "Aviasales")
PROVIDER_TUTU_BUS = AffiliateProvider("tutu_bus", "Tutu bus")
PROVIDER_TUTU_TRAIN = AffiliateProvider("tutu_train", "Tutu train")
PROVIDER_BOOKING = AffiliateProvider("booking", "Booking")


def detect_provider(url: str) -> AffiliateProvider | None:
    host = (urlparse(url).netloc or "").lower().removeprefix("www.")
    if not host:
        return None
    if host in ("aviasales.ru", "aviasales.com", "search.aviasales.ru", "search.aviasales.com"):
        return PROVIDER_AVIASALES
    if host == "bus.tutu.ru":
        return PROVIDER_TUTU_BUS
    if host == "tutu.ru" and "/poezda/" in url:
        return PROVIDER_TUTU_TRAIN
    if host in ("booking.com", "www.booking.com"):
        return PROVIDER_BOOKING
    return None


def provider_enabled(provider: AffiliateProvider) -> bool:
    if provider.key == "aviasales":
        return affiliate_aviasales_enabled()
    if provider.key == "tutu_bus":
        return affiliate_tutu_bus_enabled()
    if provider.key == "tutu_train":
        return affiliate_tutu_train_enabled()
    if provider.key == "booking":
        return affiliate_booking_enabled()
    return False
