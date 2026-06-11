"""Формат sub_id для статистики Travelpayouts."""

from __future__ import annotations

from search.affiliate.programs import AffiliateProvider


def build_sub_id(trip_id: int, channel: str, provider: AffiliateProvider) -> str:
    return f"trip_{trip_id}_{channel}_{provider.key}"
