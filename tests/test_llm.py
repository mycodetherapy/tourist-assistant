"""Тесты конфигурации LLM."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from agents.llm import _get_llm_cached
from config.settings import DEFAULT_LLM_BASE_URL, LLM_MODEL, is_placeholder_secret


class TestLlmConfig(unittest.TestCase):
    def test_placeholder_api_key(self) -> None:
        self.assertTrue(is_placeholder_secret("sk-..."))
        self.assertFalse(is_placeholder_secret("sk-live-abcd1234efgh5678"))

    @patch.dict(
        os.environ,
        {
            "LLM_API_KEY": "sk-test-key",
            "LLM_BASE_URL": "https://example.com/v1",
            "LLM_MODEL": "gpt-test",
        },
        clear=False,
    )
    def test_get_llm_uses_env(self) -> None:
        _get_llm_cached.cache_clear()
        llm = _get_llm_cached()
        self.assertEqual(llm.model_name, "gpt-test")
        self.assertEqual(str(llm.openai_api_base), "https://example.com/v1")
        self.assertEqual(llm.openai_api_key.get_secret_value(), "sk-test-key")

    @patch.dict(os.environ, {"LLM_API_KEY": "sk-test-key"}, clear=True)
    def test_get_llm_defaults(self) -> None:
        _get_llm_cached.cache_clear()
        llm = _get_llm_cached()
        self.assertEqual(llm.model_name, LLM_MODEL)
        self.assertEqual(str(llm.openai_api_base), DEFAULT_LLM_BASE_URL)


if __name__ == "__main__":
    unittest.main()
