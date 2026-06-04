"""Тесты роутинга LLM (ru vs intl)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from agents.llm import (
    _can_fallback_ru_to_intl,
    _is_placeholder_folder_id,
    _llm_config_issues,
    infer_llm_region,
)
from config.settings import is_placeholder_secret


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

    def test_placeholder_folder_id(self) -> None:
        self.assertTrue(_is_placeholder_folder_id("<folder_id>"))
        self.assertTrue(_is_placeholder_folder_id(""))
        self.assertFalse(_is_placeholder_folder_id("b1g2folder3example"))

    def test_placeholder_api_key(self) -> None:
        self.assertTrue(is_placeholder_secret("sk-..."))
        self.assertFalse(is_placeholder_secret("sk-live-abcd1234efgh5678"))

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-..."}, clear=False)
    def test_fallback_disabled_for_placeholder_key(self) -> None:
        self.assertFalse(_can_fallback_ru_to_intl())

    @patch.dict(
        os.environ,
        {
            "LLM_MODEL_RU": "gpt://<folder_id>/aliceai-llm/latest",
            "PROXY_BASE_URL_RU": "https://llm.api.cloud.yandex.net/v1",
            "YANDEX_API_KEY": "test-key",
        },
        clear=False,
    )
    def test_llm_config_issues_yandex_placeholder(self) -> None:
        issues = _llm_config_issues(region="ru")
        self.assertTrue(any("folder_id" in issue.lower() for issue in issues))

    @patch.dict(
        os.environ,
        {
            "LLM_MODEL_RU": "gpt-4o-mini",
            "PROXY_BASE_URL_RU": "https://openai.api.proxyapi.ru/v1",
        },
        clear=False,
    )
    def test_llm_config_issues_proxyapi_ok(self) -> None:
        self.assertEqual(_llm_config_issues(region="ru"), [])


if __name__ == "__main__":
    unittest.main()

