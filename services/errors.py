"""Человекочитаемые сообщения об ошибках выполнения графа."""

from __future__ import annotations


def format_runtime_error(exc: Exception) -> str:
    """Преобразует типичные сбои LLM API в понятный текст."""
    text = str(exc)
    if "length" in text.lower() or "LengthFinishReason" in type(exc).__name__:
        return (
            "Ответ LLM обрезан по лимиту токенов (слишком большой контекст или программа).\n"
            "Повторите пересбор по разделам (билеты / мероприятия / питание) или сократите запрос.\n"
            f"Детали: {text}"
        )
    if any(
        marker in text
        for marker in ("401", "Invalid API Key", "AuthenticationError", "authentication")
    ):
        return (
            "Ошибка аутентификации LLM (401): провайдер не принял LLM_API_KEY.\n"
            "Проверьте .env: ключ с https://openrouter.ai/keys (не sk-or-... из .env.example).\n"
            f"Детали: {text}"
        )
    if "403" in text or "unsupported_country_region_territory" in text:
        return (
            "Ошибка LLM (403): провайдер OpenAI недоступен из вашего региона.\n"
            "По умолчанию запросы идут через Azure (LLM_OPENROUTER_PROVIDERS).\n"
            "Если ошибка остаётся — VPN или другая модель в LLM_MODEL.\n"
            f"Детали: {text}"
        )
    if "All providers have been ignored" in text:
        return (
            "Ошибка LLM (404): OpenRouter не нашёл провайдера для модели.\n"
            "Расширьте LLM_OPENROUTER_PROVIDERS или проверьте ignore в "
            "https://openrouter.ai/settings/privacy .\n"
            f"Детали: {text}"
        )
    if "No endpoints found that support tool use" in text:
        return (
            "Ошибка LLM (404): у выбранных провайдеров нет поддержки tool calling.\n"
            "Для openai/gpt-4o-mini tools доступны только через OpenAI (VPN из РФ).\n"
            "Рекомендуется: LLM_MODEL=openai/gpt-4.1-mini, LLM_OPENROUTER_PROVIDERS=Azure\n"
            f"Детали: {text}"
        )
    if "messages with role 'tool'" in text or "tool_calls" in text:
        return (
            "Ошибка LLM (400): некорректная история сообщений для API.\n"
            "Перезапустите python3 main.py. Если повторяется — сообщите об ошибке.\n"
            f"Детали: {text}"
        )
    return f"Ошибка выполнения: {text}"
