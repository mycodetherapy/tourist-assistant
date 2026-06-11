"""Тесты URL поиска Aviasales."""

from __future__ import annotations

import unittest
from datetime import date

from search.aviasales_urls import build_aviasales_search_url


class TestAviasalesUrls(unittest.TestCase):
    def test_round_trip_path(self) -> None:
        url = build_aviasales_search_url(
            "GSV",
            "MOW",
            date(2026, 7, 15),
            date(2026, 7, 18),
        )
        self.assertIn("/search/GSV1507MOW1807", url)
        self.assertIn("origin_airports=0", url)
        self.assertIn("destination_airports=1", url)
        self.assertNotIn("?t=DP", url)

    def test_affiliate_marker(self) -> None:
        url = build_aviasales_search_url(
            "MOW",
            "LED",
            date(2026, 7, 15),
            affiliate_marker="123456",
        )
        self.assertIn("marker=123456", url)


if __name__ == "__main__":
    unittest.main()
