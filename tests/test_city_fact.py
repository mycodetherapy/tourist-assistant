"""Тесты факта о городе (Wikidata → polish → validation)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from agents.city_fact import (
    generate_city_fact,
    is_boring_city_fact,
    is_valid_city_fact,
    polish_city_fact_llm,
)


class CityFactValidationTests(unittest.TestCase):
    def test_valid_fact(self) -> None:
        text = (
            "Казань основана в 1005 году и стала столицей Казанского ханства. "
            "В 1552 году город взял Иван Грозный; Казанский кремль XVI века — объект UNESCO. "
            "Рядом — улица Баумана и татарский старогород. Город на слиянии Волги и Казанки "
            "сочетает мусульманское и православное наследие, сюда едут за историей Поволжья."
        )
        self.assertTrue(is_valid_city_fact(text))

    def test_rejects_boring_admin_fact(self) -> None:
        text = (
            "Брянск — крупный город на западе России. "
            "Он является административным центром Брянской области."
        )
        self.assertTrue(is_boring_city_fact(text))
        self.assertFalse(is_valid_city_fact(text))

    def test_rejects_short(self) -> None:
        self.assertFalse(is_valid_city_fact("Коротко."))

    def test_rejects_url(self) -> None:
        text = "Город интересен туристам. Подробнее: https://example.com/wiki " + "x" * 40
        self.assertFalse(is_valid_city_fact(text))

    def test_rejects_museum_list(self) -> None:
        text = (
            "- Музей 1\n- Музей 2\n- Музей 3\n"
            "Совет: бронируйте заранее и наденьте удобную обувь."
        )
        self.assertFalse(is_valid_city_fact(text))


class CityFactGenerationTests(unittest.TestCase):
    @patch("agents.city_fact.fetch_raw_city_fact")
    @patch("agents.city_fact.get_llm_chat")
    def test_polish_llm_valid(self, mock_get_llm: MagicMock, mock_raw: MagicMock) -> None:
        mock_raw.return_value = (
            "Город: Казань\n"
            "Wikipedia: Казань — город на Волге...\n"
            "Известные места (Wikidata): Казанский кремль, улица Баумана"
        )
        fact = (
            "Казань основана в 1005 году и стала столицей Казанского ханства. "
            "Казанский кремль — объект UNESCO XVI века, рядом — улица Баумана "
            "и татарский старогород. Город на слиянии Волги и Казанки сочетает "
            "мусульманское и православное наследие, сюда едут за историей Поволжья."
        )
        mock_get_llm.return_value.bind.return_value.invoke.return_value = MagicMock(content=fact)
        out = polish_city_fact_llm(mock_raw.return_value, city="Казань")
        self.assertEqual(out, fact)

    @patch("agents.city_fact.fetch_raw_city_fact")
    @patch("agents.city_fact.polish_city_fact_llm")
    def test_generate_without_llm_fallback(
        self, mock_polish: MagicMock, mock_raw: MagicMock
    ) -> None:
        mock_raw.return_value = (
            "Город: Казань\n"
            "Wikipedia: Казань основана в 1005 году и стала столицей Казанского ханства. "
            "В 1552 году город вошёл в состав России; Казанский кремль XVI века — объект UNESCO. "
            "Улица Баумана и старый татарский город привлекают прогулки у слияния Волги и Казанки."
        )
        out = generate_city_fact(city="Казань", use_llm=False)
        mock_polish.assert_not_called()
        self.assertGreaterEqual(len(out), 80)
        self.assertIn("Казань", out)


if __name__ == "__main__":
    unittest.main()
