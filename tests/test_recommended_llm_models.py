"""Проверка рекомендованных моделей на OpenRouter (tools + structured output)."""

from __future__ import annotations

import json
import unittest
import urllib.request

from config.settings import LLM_MODEL, RECOMMENDED_ALTERNATIVE_LLM_MODELS


def _supports_app_requirements(model_id: str, providers: tuple[str, ...]) -> bool:
    """На одном из провайдеров должны быть tools и structured output."""
    url = f"https://openrouter.ai/api/v1/models/{model_id}/endpoints"
    with urllib.request.urlopen(url, timeout=30) as response:
        endpoints = json.load(response)["data"]["endpoints"]
    wanted = set(providers)
    for endpoint in endpoints:
        if endpoint.get("provider_name") not in wanted:
            continue
        params = set(endpoint.get("supported_parameters") or [])
        has_tools = "tools" in params
        has_struct = "structured_outputs" in params or "response_format" in params
        if has_tools and has_struct:
            return True
    return False


def _azure_supports_app_requirements(model_id: str) -> bool:
    return _supports_app_requirements(model_id, ("Azure",))


@unittest.skipUnless(
    __import__("os").getenv("RUN_OPENROUTER_MODEL_CHECKS", "1") == "1",
    "set RUN_OPENROUTER_MODEL_CHECKS=0 to skip live OpenRouter checks",
)
class TestRecommendedLlmModels(unittest.TestCase):
    def test_default_model_on_azure(self) -> None:
        self.assertEqual(LLM_MODEL, "openai/gpt-4.1-mini")
        self.assertTrue(_azure_supports_app_requirements(LLM_MODEL))

    def test_alternative_models(self) -> None:
        self.assertEqual(len(RECOMMENDED_ALTERNATIVE_LLM_MODELS), 5)
        openai_count = sum(
            1 for model_id, _ in RECOMMENDED_ALTERNATIVE_LLM_MODELS
            if model_id.startswith("openai/")
        )
        self.assertEqual(openai_count, 1)
        for model_id, providers in RECOMMENDED_ALTERNATIVE_LLM_MODELS:
            with self.subTest(model=model_id, providers=providers):
                self.assertTrue(
                    _supports_app_requirements(model_id, providers),
                    f"{model_id}: нет tools/structured_outputs на {providers}",
                )


if __name__ == "__main__":
    unittest.main()
