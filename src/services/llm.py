import os
from typing import Any

from langchain_openai import ChatOpenAI

from src.config import Settings, get_settings

# Tắt LangSmith tracing nếu không có API key hợp lệ
if not os.environ.get("LANGCHAIN_API_KEY"):
    os.environ["LANGCHAIN_TRACING_V2"] = "false"


PROVIDER_DEFAULTS = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-1.5-flash",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
    },
    "mimo": {
        "base_url": "https://api.xiaomimimo.com/v1",
        "model": "mimo-v2.5",
    },
}


def _resolve_llm_config(settings: Settings) -> tuple[str, str | None, str]:
    """Determine effective API key, base URL, and model name based on provider."""
    provider = settings.llm_provider.lower().strip()
    preset = PROVIDER_DEFAULTS.get(provider, {})

    if provider == "groq":
        api_key = settings.groq_api_key or settings.openai_api_key
    elif provider == "gemini":
        api_key = settings.google_api_key or settings.openai_api_key
    elif provider == "mimo":
        api_key = settings.mimo_api_key or settings.openai_api_key
    else:
        api_key = settings.openai_api_key

    base_url = settings.openai_api_base or preset.get("base_url")
    model_name = settings.model_name or preset.get("model", "gpt-4o-mini")

    return api_key, base_url, model_name


def get_llm() -> ChatOpenAI:
    """Instantiate and return configured ChatOpenAI client supporting multiple providers."""
    settings = get_settings()
    api_key, base_url, model_name = _resolve_llm_config(settings)

    kwargs: dict[str, Any] = {
        "model": model_name,
        "api_key": api_key,
        "temperature": settings.llm_temperature,
    }
    if base_url:
        kwargs["base_url"] = base_url

    return ChatOpenAI(**kwargs)
