"""Тесты конфигурации LLM."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from agents.llm import _build_llm, clear_llm_cache, get_llm
from agents.llm_context import LlmConfig
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
        clear_llm_cache()
        llm = get_llm()
        self.assertEqual(llm.model_name, "gpt-test")
        self.assertEqual(str(llm.openai_api_base), "https://example.com/v1")
        self.assertEqual(llm.openai_api_key.get_secret_value(), "sk-test-key")

    @patch.dict(os.environ, {"LLM_API_KEY": "sk-test-key"}, clear=True)
    def test_get_llm_defaults(self) -> None:
        clear_llm_cache()
        llm = get_llm()
        self.assertEqual(llm.model_name, LLM_MODEL)
        self.assertEqual(str(llm.openai_api_base), DEFAULT_LLM_BASE_URL)

    def test_build_llm_skips_openrouter_provider_for_proxy(self) -> None:
        llm = _build_llm(
            LlmConfig(
                api_key="sk-test",
                base_url="https://api.proxyapi.ru/openai/v1",
                model="gpt-4.1-mini",
            )
        )
        self.assertEqual(str(llm.openai_api_base), "https://api.proxyapi.ru/openai/v1")
        self.assertNotIn("extra_body", llm.model_kwargs)


if __name__ == "__main__":
    unittest.main()
