"""Тесты извлечения названий достопримечательностей из веб-поиска."""

from __future__ import annotations

import unittest

from search.yandex.landmark_discovery import (
    extract_landmark_names,
    geocode_query_for_name,
    infer_tag_for_name,
)


class TestLandmarkDiscovery(unittest.TestCase):
    def test_extracts_named_places_from_snippets(self) -> None:
        payload = {
            "answer": (
                "1. Национальная художественная галерея Республики Марий Эл\n"
                "2. набережная Брюгге\n"
                "3. парк культуры и отдыха имени 400-летия Йошкар-Олы"
            ),
            "results": [
                {
                    "title": "Площадь Республики Пресвятой Девы Марии — Йошкар-Ола",
                    "snippet": "Рядом находится Центральный парк культуры и отдыха.",
                },
            ],
        }
        names = extract_landmark_names(payload, city="Йошкар-Ола")
        joined = " | ".join(names)
        self.assertIn("набережная Брюгге", joined)
        self.assertTrue(
            any("400-летия" in n or "парк культуры" in n.lower() for n in names)
        )
        self.assertTrue(
            any("галере" in n.lower() for n in names)
            or any("площад" in n.lower() for n in names)
        )

    def test_geocode_query_appends_city(self) -> None:
        self.assertEqual(
            geocode_query_for_name("набережная Брюгге", "Йошкар-Ола"),
            "набережная Брюгге Йошкар-Ола",
        )
        self.assertEqual(
            geocode_query_for_name(
                "парк культуры и отдыха имени 400-летия Йошкар-Олы",
                "Йошкар-Ола",
            ),
            "парк культуры и отдыха имени 400-летия Йошкар-Олы",
        )

    def test_infer_tag_from_name(self) -> None:
        self.assertEqual(infer_tag_for_name("набережная Брюгге"), "embankments")
        self.assertEqual(infer_tag_for_name("Центральный парк"), "parks")
        self.assertEqual(infer_tag_for_name("Республиканский музей"), "museums")


if __name__ == "__main__":
    unittest.main()
