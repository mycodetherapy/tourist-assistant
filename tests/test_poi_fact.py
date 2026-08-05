"""Тесты справки по POI."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from agents.poi_fact import (
    POI_FACT_NOT_FOUND,
    generate_poi_fact,
    generate_poi_fact_llm,
    fetch_poi_fact_wikipedia,
    is_valid_poi_fact,
    looks_like_city_article,
    poi_fact_user_prompt,
)
from search.poi_fact_sources import (
    PoiFactContext,
    extract_wikidata_qid,
    infer_source_kind,
    normalize_cache_key,
)
from search.wikidata.city_description import normalize_wiki_title


class TestPoiFactCacheKey(unittest.TestCase):
    def test_wikidata_qid(self) -> None:
        self.assertEqual(extract_wikidata_qid("Q12345"), "Q12345")
        self.assertEqual(extract_wikidata_qid("wikidata_Q99"), "Q99")

    def test_normalize_cache_key(self) -> None:
        self.assertEqual(
            normalize_cache_key(poi_id="Q42", name="Кремль", city="Казань"),
            "Q42",
        )
        key_a = normalize_cache_key(poi_id=None, name="Собор", city="Саратов")
        key_b = normalize_cache_key(poi_id=None, name="Собор", city="Саратов")
        self.assertTrue(key_a.startswith("search_"))
        self.assertEqual(key_a, key_b)

    def test_infer_source_kind(self) -> None:
        self.assertEqual(infer_source_kind("Q1"), "wikidata")
        self.assertEqual(infer_source_kind("osm_node_9"), "osm")
        self.assertEqual(infer_source_kind(""), "search")


class TestPoiFactPrompt(unittest.TestCase):
    def test_user_prompt(self) -> None:
        prompt = poi_fact_user_prompt(
            name="Царевококшайский кремль",
            city="Йошкар-Ола",
        )
        self.assertIn("Йошкар-Ола", prompt)
        self.assertIn("Царевококшайский кремль", prompt)
        self.assertIn("историческую справку", prompt)


class TestPoiFactValidation(unittest.TestCase):
    def test_valid_poi_fact(self) -> None:
        text = (
            "Казанский кремль — крепость XVI века на высоком берегу Волги, "
            "включённая в список UNESCO в 2000 году. Здесь мечеть Кул-Шариф, "
            "восстановленная к 1000-летию Казани в 2005 году, башня Сююмбике "
            "и музеи, рассказывающие об истории Казанского ханства и присоединения "
            "города к России в 1552 году. Архитектура сочетает татарские и русские "
            "традиции; комплекс открыт для экскурсий и прогулок по стенам."
        )
        self.assertTrue(is_valid_poi_fact(text))

    def test_city_article_detected(self) -> None:
        text = "город в России, столица Республики Марий Эл, административный центр"
        self.assertTrue(looks_like_city_article(text))


class TestPoiFactLlm(unittest.TestCase):
    @patch("agents.poi_fact.get_llm_chat")
    def test_generate_poi_fact_llm(self, mock_get_llm) -> None:
        response = MagicMock()
        response.content = (
            "Царевококшайский кремль в Йошкар-Оле — историческая крепость, "
            "заложенная в 1584 году как Царевококшайск. Деревянные валы и башни "
            "сохранялись до конца XVII века; в 2009 году открыт культурно-исторический "
            "комплекс с музеем и реконструкцией построек. Сюда приходят за прогулкой "
            "по валам и знакомством с историей марийского края и правления Ивана Грозного; "
            "на территории проводятся экскурсии и тематические фестивали."
        )
        mock_get_llm.return_value.bind.return_value.invoke.return_value = response
        text = generate_poi_fact_llm(name="Царевококшайский кремль", city="Йошкар-Ола")
        self.assertIn("кремль", text.lower())

    @patch("agents.poi_fact.generate_poi_fact_llm")
    def test_generate_poi_fact(self, mock_llm) -> None:
        mock_llm.return_value = (
            "Академический русский театр драмы имени Георгия Константинова — "
            "государственный театр Йошкар-Олы. Русская труппа работает в городе "
            "с 1919 года, самостоятельный сезон открылся в 1937 году спектаклем "
            "«Платон Кречет». С 1964 по 1994 год главным режиссёром был Г. В. Константинов, "
            "в честь которого театр назван; здание — памятник архитектуры советского периода."
        )
        ctx = PoiFactContext(
            cache_key="search_test",
            poi_id="osm_node_1",
            name="Академический русский театр драмы им. Георгия Константинова",
            city="Йошкар-Ола",
            source_kind="osm",
            wikidata_qid=None,
        )
        result = generate_poi_fact(ctx)
        self.assertTrue(result.used_llm)
        self.assertEqual(result.source_kind, "llm")
        self.assertIn("театр", result.text.lower())


class TestPoiFactWikipedia(unittest.TestCase):
    @patch("search.wikidata.city_description.search_wikipedia_titles")
    @patch("search.wikidata.city_description.city_wikipedia_titles")
    def test_skips_city_article_in_search(
        self,
        mock_city_titles,
        mock_search,
    ) -> None:
        mock_city_titles.return_value = {normalize_wiki_title("Йошкар-Ола")}
        mock_search.side_effect = [
            [
                "Йошкар-Ола",
                "Национальный музей Республики Марий Эл",
            ],
            [],
        ]

        city_text = (
            "город в России, столица Республики Марий Эл, административный центр "
            "городского округа, население 285219"
        )
        museum_text = (
            "Национальный музей Республики Марий Эл открыт в 1959 году в Йошкар-Оле. "
            "Экспозиция рассказывает об истории марийского народа, ремёслах и "
            "культуре региона; в фондах более 100000 предметов."
        )

        def _extract(*, title: str, max_chars: int = 2200, lang: str = "ru", ellipsis: bool = False):
            if title == "Йошкар-Ола":
                return city_text
            if "музей" in title.lower():
                return museum_text
            return ""

        ctx = PoiFactContext(
            cache_key="search_test",
            poi_id="osm_node_1",
            name="Национальный музей",
            city="Йошкар-Ола",
            source_kind="osm",
            wikidata_qid=None,
        )
        with patch("search.wikidata.city_description.fetch_wikipedia_extract", side_effect=_extract):
            with patch("search.wikidata.city_description.fetch_wikipedia_lead", return_value=""):
                text = fetch_poi_fact_wikipedia(ctx)
        self.assertIn("музей", text.lower())
        self.assertNotIn("столица республики", text.lower())

    @patch("search.wikidata.city_description.fetch_wikipedia_poi_for_wikidata")
    def test_wikidata_path_without_name_match(self, mock_wiki) -> None:
        mock_wiki.return_value = (
            "Академический русский театр драмы имени Георгия Константинова — "
            "государственное автономное учреждение культуры Республики Марий Эл."
        )
        ctx = PoiFactContext(
            cache_key="Q4059185",
            poi_id="Q4059185",
            name="Академический русский театр драмы им. Георгия Константинова",
            city="Йошкар-Ола",
            source_kind="wikidata",
            wikidata_qid="Q4059185",
        )
        text = fetch_poi_fact_wikipedia(ctx)
        self.assertIn("театр", text.lower())

    @patch("search.wikidata.city_description.search_wikipedia_titles", return_value=[])
    def test_search_without_article_fails(self, _mock_search) -> None:
        ctx = PoiFactContext(
            cache_key="search_test",
            poi_id="osm_node_1",
            name="М. Шкетану",
            city="Йошкар-Ола",
            source_kind="osm",
            wikidata_qid=None,
        )
        with self.assertRaisesRegex(RuntimeError, POI_FACT_NOT_FOUND):
            fetch_poi_fact_wikipedia(ctx)


if __name__ == "__main__":
    unittest.main()
