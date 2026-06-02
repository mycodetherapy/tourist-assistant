"""Тесты роутинга LLM (ru vs intl)."""

from __future__ import annotations

import unittest

from agents.llm import infer_llm_region


class TestLlmRouting(unittest.TestCase):
    def test_infer_ru_cyrillic_city(self) -> None:
        self.assertEqual(infer_llm_region("Санкт-Петербург"), "ru")
        self.assertEqual(infer_llm_region("Москва"), "ru")

    def test_infer_ru_latin_known_city(self) -> None:
        self.assertEqual(infer_llm_region("Moscow"), "ru")
        self.assertEqual(infer_llm_region("Saint Petersburg"), "ru")

    def test_infer_intl_latin_unknown_city(self) -> None:
        self.assertEqual(infer_llm_region("Paris"), "intl")
        self.assertEqual(infer_llm_region("New York"), "intl")

    def test_infer_intl_cyrillic_foreign_hint(self) -> None:
        # Кириллица сама по себе не гарантирует РФ: "Париж" и "Токио" — зарубежье.
        self.assertEqual(infer_llm_region("Париж, Франция"), "intl")
        self.assertEqual(infer_llm_region("Токио, Япония"), "intl")


if __name__ == "__main__":
    unittest.main()

