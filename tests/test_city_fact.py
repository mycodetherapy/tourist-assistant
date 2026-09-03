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
    _VALID_FACT = (
        "Казань основана в 1005 году и стала столицей Казанского ханства. "
        "В 1552 году город взял Иван Грозный; Казанский кремль XVI века — объект UNESCO. "
        "Рядом — улица Баумана и татарский старогород. Город на слиянии Волги и Казанки "
        "сочетает мусульманское и православное наследие, сюда едут за историей Поволжья."
    )

    @patch("agents.city_fact.fetch_raw_city_fact")
    @patch("agents.city_fact.get_llm_chat")
    def test_polish_llm_valid(self, mock_get_llm: MagicMock, mock_raw: MagicMock) -> None:
        mock_raw.return_value = (
            "Город: Казань\n"
            "Wikipedia: Казань — город на Волге...\n"
            "Известные места (Wikidata): Казанский кремль, улица Баумана"
        )
        fact = self._VALID_FACT
        self.assertTrue(is_valid_city_fact(fact))
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=fact)
        mock_get_llm.return_value.bind.return_value = mock_llm
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

    @patch("agents.city_fact.fetch_raw_city_fact")
    def test_generate_without_llm_appends_wikipedia_link(
        self, mock_raw: MagicMock
    ) -> None:
        mock_raw.return_value = (
            "Город: Казань\n"
            "Wikipedia: Казань основана в 1005 году и стала столицей Казанского ханства. "
            "В 1552 году город вошёл в состав России; Казанский кремль XVI века — объект UNESCO. "
            "Улица Баумана и старый татарский город привлекают прогулки у слияния Волги и Казанки.\n"
            "Wikipedia-URL: https://ru.wikipedia.org/wiki/%D0%9A%D0%B0%D0%B7%D0%B0%D0%BD%D1%8C"
        )
        out = generate_city_fact(city="Казань", use_llm=False)
        self.assertIn("Казань", out)
        self.assertIn("Читать далее в Wikipedia", out)
        self.assertIn("wikipedia.org/wiki/", out)
        preview = out.split("[Читать")[0].strip()
        self.assertRegex(preview, r"[.!?]\s*…$")
        self.assertNotRegex(preview, r"\w…$")

    @patch("agents.city_fact.fetch_raw_city_fact")
    @patch("agents.city_fact.polish_city_fact_llm")
    def test_generate_with_llm_appends_wikipedia_link(
        self, mock_polish: MagicMock, mock_raw: MagicMock
    ) -> None:
        mock_raw.return_value = (
            "Город: Казань\n"
            "Wikipedia: источник\n"
            "Wikipedia-URL: https://ru.wikipedia.org/wiki/Казань"
        )
        mock_polish.return_value = self._VALID_FACT
        out = generate_city_fact(city="Казань", use_llm=True)
        self.assertEqual(out.split("[Читать")[0].strip(), self._VALID_FACT)
        self.assertIn("Читать далее в Wikipedia", out)
        self.assertIn("wikipedia.org/wiki/", out)
        self.assertNotIn(" …\n\n[", out)

    def test_valid_fact_ignores_wikipedia_read_more(self) -> None:
        text = (
            self._VALID_FACT
            + "\n\n[Читать далее в Wikipedia](https://ru.wikipedia.org/wiki/Казань)"
        )
        self.assertTrue(is_valid_city_fact(text))

    def test_llm_trim_drops_mid_sentence(self) -> None:
        from search.wikidata.city_description import trim_to_semantic_boundary

        cut = self._VALID_FACT + " Следующая фраза обрывается на полуслове Казан"
        out = trim_to_semantic_boundary(cut, 2800, ellipsis=False)
        self.assertTrue(out.endswith((".", "!", "?")))
        self.assertFalse(out.endswith("Казан"))
        self.assertIn("Поволжья.", out)

    def test_trim_long_text_at_sentence(self) -> None:
        from search.wikidata.city_description import trim_to_semantic_boundary

        sentence = "Казань основана в 1005 году и известна кремлём XVI века. "
        blob = sentence * 80
        out = trim_to_semantic_boundary(blob, 800, ellipsis=True)
        self.assertLessEqual(len(out), 810)
        self.assertRegex(out, r"[.!?]\s*…$")
        self.assertNotRegex(out, r"\w…$")

    def test_trim_rolls_back_initial_and_list_item(self) -> None:
        from search.wikidata.city_description import (
            drop_incomplete_sentence,
            trim_to_semantic_boundary,
        )

        cut = (
            "В городе работают Марийский государственный университет, "
            "Марийский национальный театр драмы имени М."
        )
        dropped = drop_incomplete_sentence(cut)
        self.assertIn("университет", dropped)
        self.assertNotIn("имени М.", dropped)
        out = trim_to_semantic_boundary(cut, 2800, ellipsis=True)
        self.assertIn("университет", out)
        self.assertNotIn("имени М.", out)
        self.assertTrue(out.endswith("…"))

    def test_keeps_initial_inside_complete_sentence(self) -> None:
        from search.wikidata.city_description import drop_incomplete_sentence

        full = (
            "Марийский национальный театр драмы имени М. Шкетана открыт в 1919 году."
        )
        self.assertEqual(drop_incomplete_sentence(full), full)


if __name__ == "__main__":
    unittest.main()
