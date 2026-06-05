"""Тесты OpenRouter provider routing."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from config.settings import (
    DEFAULT_OPENROUTER_PROVIDERS,
    LLM_MODEL,
    get_llm_extra_body,
    get_openrouter_providers,
)


class TestOpenRouterConfig(unittest.TestCase):
    def test_default_model_supports_azure_tools(self) -> None:
        self.assertEqual(LLM_MODEL, "openai/gpt-4.1-mini")

    @patch.dict(os.environ, {"LLM_BASE_URL": "https://openrouter.ai/api/v1"}, clear=False)
    def test_default_only_azure(self) -> None:
        for key in (
            "LLM_OPENROUTER_PROVIDERS",
            "LLM_OPENROUTER_PROVIDER_ORDER",
            "LLM_OPENROUTER_PROVIDER_IGNORE",
        ):
            os.environ.pop(key, None)
        body = get_llm_extra_body()
        self.assertIsNotNone(body)
        provider = body["provider"]  # type: ignore[index]
        self.assertEqual(provider["only"], list(DEFAULT_OPENROUTER_PROVIDERS))
        self.assertEqual(provider["only"], ["Azure"])
        self.assertTrue(provider["require_parameters"])
        self.assertFalse(provider["allow_fallbacks"])

    @patch.dict(
        os.environ,
        {"LLM_OPENROUTER_PROVIDERS": "Azure, DeepInfra"},
        clear=False,
    )
    def test_custom_providers(self) -> None:
        self.assertEqual(get_openrouter_providers(), ["Azure", "DeepInfra"])

    @patch.dict(
        os.environ,
        {
            "LLM_BASE_URL": "https://openrouter.ai/api/v1",
            "LLM_OPENROUTER_PROVIDERS": "",
        },
        clear=False,
    )
    def test_empty_providers_allows_any(self) -> None:
        body = get_llm_extra_body()
        self.assertIsNotNone(body)
        provider = body["provider"]  # type: ignore[index]
        self.assertTrue(provider["allow_fallbacks"])
        self.assertTrue(provider["require_parameters"])
        self.assertNotIn("only", provider)

    @patch.dict(os.environ, {"LLM_BASE_URL": "https://example.com/v1"}, clear=False)
    def test_no_extra_body_for_non_openrouter(self) -> None:
        self.assertIsNone(get_llm_extra_body())


if __name__ == "__main__":
    unittest.main()
