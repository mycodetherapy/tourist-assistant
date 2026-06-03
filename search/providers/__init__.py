"""Провайдеры внешних API для билетов."""

from search.providers.avia import fetch_avia_offers

__all__ = ["fetch_avia_offers"]
