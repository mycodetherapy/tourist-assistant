"""Тесты извлечения названий достопримечательностей из веб-поиска."""

from __future__ import annotations

import unittest

from search.yandex.landmark_discovery import (
    extract_landmark_names,
    geocode_query_for_name,
    infer_tag_for_name,
)

_CITY = "Самара"


class TestLandmarkDiscovery(unittest.TestCase):
    def test_extracts_named_places_from_snippets(self) -> None:
        payload = {
            "answer": (
                "1. Самарский художественный музей\n"
                "2. Волжская набережная\n"
                "3. парк культуры и отдыха имени Горького"
            ),
            "results": [
                {
                    "title": "Площадь Куйбышева — Самара",
                    "snippet": "Рядом находится Центральный парк культуры и отдыха.",
                },
            ],
        }
        names = extract_landmark_names(payload, city=_CITY)
        joined = " | ".join(names)
        self.assertIn("Волжская набережная", joined)
        self.assertTrue(
            any("парк культуры" in n.lower() for n in names)
        )
        self.assertTrue(
            any("музе" in n.lower() for n in names)
            or any("площад" in n.lower() for n in names)
        )

    def test_geocode_query_appends_city_when_absent(self) -> None:
        self.assertEqual(
            geocode_query_for_name("Волжская набережная", _CITY),
            "Волжская набережная Самара",
        )

    def test_geocode_query_keeps_name_when_city_present(self) -> None:
        self.assertEqual(
            geocode_query_for_name("парк культуры и отдыха Самара", _CITY),
            "парк культуры и отдыха Самара",
        )

    def test_infer_tag_from_name(self) -> None:
        self.assertEqual(infer_tag_for_name("Волжская набережная"), "embankments")
        self.assertEqual(infer_tag_for_name("Центральный парк"), "parks")
        self.assertEqual(infer_tag_for_name("Республиканский музей"), "museums")

    def test_format_discovery_digest(self) -> None:
        from search.yandex.landmark_discovery import (
            LandmarkDiscoveryTrace,
            format_landmark_discovery_digest,
        )

        digest = format_landmark_discovery_digest(
            LandmarkDiscoveryTrace(
                provider="tavily",
                queries=[f"достопримечательности {_CITY}"],
                results_count=2,
                raw_results_count=5,
                search_results=[
                    {
                        "title": "Что посмотреть",
                        "url": "https://example.com",
                        "snippet": "Волжская набережная",
                    }
                ],
                landmark_names=["Волжская набережная"],
                geocode_queries=[
                    {"name": "Волжская набережная", "query": "Волжская набережная Самара"}
                ],
            )
        )
        self.assertIn("tavily", digest)
        self.assertIn("Волжская набережная", digest)
        self.assertIn("match", digest)


if __name__ == "__main__":
    unittest.main()
