import logging
import os
from typing import Any

from langchain_openai import ChatOpenAI

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Tắt LangSmith tracing nếu không có API key hợp lệ hoặc LANGCHAIN_TRACING_V2=false
_langchain_key = os.environ.get("LANGCHAIN_API_KEY", "").strip()
_tracing_val = os.environ.get("LANGCHAIN_TRACING_V2", "false").strip().lower()

if (
    not _langchain_key
    or _langchain_key in ("your-langsmith-key-here", "dummy", "none")
    or _tracing_val in ("false", "0", "off", "no")
):
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ.pop("LANGCHAIN_API_KEY", None)

# Default model per provider (fallback when MODEL_NAME is empty)
_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-1.5-flash",
    "groq": "llama-3.3-70b-versatile",
    "mimo": "mimo-v2.5",
}


def _resolve_llm_config(
    settings: Settings,
) -> tuple[str, str, str]:
    """Determine API key, base URL, and model name."""
    provider = settings.llm_provider.lower().strip()

    # Resolve API key
    if provider == "groq":
        api_key = settings.groq_api_key or settings.openai_api_key
    elif provider == "gemini":
        api_key = settings.google_api_key or settings.openai_api_key
    elif provider == "mimo":
        api_key = settings.mimo_api_key or settings.openai_api_key
    else:
        api_key = settings.openai_api_key

    # Resolve base URL from per-provider config field
    base_url_map = {
        "openai": settings.openai_api_base,
        "gemini": settings.google_api_base,
        "groq": settings.groq_api_base,
        "mimo": settings.mimo_api_base,
    }
    base_url = base_url_map.get(provider, settings.openai_api_base)

    # Resolve model name
    default_model = _DEFAULT_MODELS.get(provider, "gpt-4o-mini")
    model_name = settings.model_name or default_model

    return api_key, base_url, model_name


def get_llm() -> ChatOpenAI:
    """Instantiate ChatOpenAI client with provider config."""
    settings = get_settings()
    api_key, base_url, model_name = _resolve_llm_config(settings)

    logger.info(
        "Instantiating LLM client (provider=%s, model=%s, base_url=%s)",
        settings.llm_provider,
        model_name,
        base_url or "default",
    )

    kwargs: dict[str, Any] = {
        "model": model_name,
        "api_key": api_key,
        "temperature": settings.llm_temperature,
    }
    if base_url:
        kwargs["base_url"] = base_url

    return ChatOpenAI(**kwargs)
