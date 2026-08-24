import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlparse

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from src.config import Settings, get_settings, reload_settings

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

# Alternative spellings accepted for LLM_PROVIDER
_PROVIDER_ALIASES = {"google": "gemini", "claude": "anthropic"}

# Default model per provider (fallback when MODEL_NAME / LLM_MODEL are empty)
_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-1.5-flash",
    "groq": "openai/gpt-oss-120b",
    "mimo": "mimo-v2.5",
    "anthropic": "claude-sonnet-5",
}

# Wire protocol per provider — providers not listed speak the OpenAI protocol
_PROTOCOL_BY_PROVIDER = {"anthropic": "anthropic"}

# Settings field holding the model override for each call site role
_ROLE_MODEL_FIELDS = {
    "enrich": "llm_model_enrich",
    "metric": "llm_model_metric",
}

# Hosts that serve OpenAI-compatible endpoints without requiring an API key
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1", "host.docker.internal"})

# Placeholder key for local endpoints — chat clients reject an empty key
_NO_KEY_PLACEHOLDER = "not-needed"

_ENV_FILE = Path(".env")


class LLMConfig(NamedTuple):
    """Resolved LLM connection settings (also the client cache key)."""

    provider: str
    protocol: str
    api_key: str
    base_url: str
    model: str
    temperature: float


def _provider_api_keys(settings: Settings) -> dict[str, str]:
    return {
        "openai": settings.openai_api_key,
        "gemini": settings.google_api_key,
        "groq": settings.groq_api_key,
        "mimo": settings.mimo_api_key,
        "anthropic": settings.anthropic_api_key,
    }


def _provider_base_urls(settings: Settings) -> dict[str, str]:
    return {
        "openai": settings.openai_api_base,
        "gemini": settings.google_api_base,
        "groq": settings.groq_api_base,
        "mimo": settings.mimo_api_base,
        "anthropic": settings.anthropic_api_base,
    }


def _resolve_provider(settings: Settings) -> str:
    """Normalize LLM_PROVIDER and map known aliases (google -> gemini)."""
    provider = settings.llm_provider.lower().strip()
    return _PROVIDER_ALIASES.get(provider, provider)


def _resolve_api_key(settings: Settings, provider: str) -> str:
    """LLM_API_KEY > <PROVIDER>_API_KEY > OPENAI_API_KEY."""
    if settings.llm_api_key:
        return settings.llm_api_key.strip()
    per_provider = _provider_api_keys(settings).get(provider, "")
    return (per_provider or settings.openai_api_key).strip()


def _resolve_base_url(settings: Settings, provider: str) -> str:
    """LLM_API_BASE > <PROVIDER>_API_BASE > "" (unknown provider)."""
    base_url = settings.llm_api_base or _provider_base_urls(settings).get(provider, "")
    return base_url.strip().rstrip("/")


def _resolve_role_model(settings: Settings, role: str | None) -> str:
    """Return LLM_MODEL_<ROLE> for a known role, or "" when unset."""
    if role is None:
        return ""
    field = _ROLE_MODEL_FIELDS.get(role)
    if field is None:
        raise ValueError(f"Unknown LLM role '{role}'. Valid roles: {', '.join(sorted(_ROLE_MODEL_FIELDS))}.")
    return str(getattr(settings, field, "")).strip()


def _resolve_model(settings: Settings, provider: str, role: str | None = None) -> str:
    """LLM_MODEL_<ROLE> > LLM_MODEL > MODEL_NAME > per-provider default."""
    role_model = _resolve_role_model(settings, role)
    if role_model:
        return role_model
    model = settings.llm_model or settings.model_name
    return (model or _DEFAULT_MODELS.get(provider, "gpt-4o-mini")).strip()


def _resolve_protocol(settings: Settings, provider: str) -> str:
    """LLM_PROTOCOL > protocol implied by the provider > "openai"."""
    protocol = settings.llm_protocol.lower().strip() or _PROTOCOL_BY_PROVIDER.get(provider, "openai")
    if protocol not in _CLIENT_BUILDERS:
        raise ValueError(
            f"LLM_PROTOCOL='{protocol}' is not supported. Supported protocols: {', '.join(sorted(_CLIENT_BUILDERS))}."
        )
    return protocol


def _is_local_endpoint(base_url: str) -> bool:
    """True when base_url points at a local endpoint that needs no API key."""
    hostname = urlparse(base_url).hostname
    return hostname in _LOCAL_HOSTS if hostname else False


def _required_judge_values(settings: Settings) -> tuple[str, str, str]:
    """Return mandatory Judge provider, key, and model settings."""
    values = (
        (settings.judge_llm_provider.strip(), "JUDGE_LLM_PROVIDER is required"),
        (settings.judge_api_key.strip(), "JUDGE_API_KEY is required"),
        (settings.judge_model_name.strip(), "JUDGE_MODEL_NAME is required"),
    )
    for value, message in values:
        if not value:
            raise ValueError(message)
    return values[0][0], values[1][0], values[2][0]


def _resolve_judge_protocol(settings: Settings, provider: str) -> str:
    """Resolve the dedicated Judge wire protocol."""
    protocol = settings.judge_llm_protocol.lower().strip() or _PROTOCOL_BY_PROVIDER.get(provider, "openai")
    if protocol not in _CLIENT_BUILDERS:
        supported = ", ".join(sorted(_CLIENT_BUILDERS))
        raise ValueError(f"JUDGE_LLM_PROTOCOL='{protocol}' is not supported. Supported protocols: {supported}.")
    return protocol


def _validate_judge_isolation(agent: LLMConfig, judge: LLMConfig) -> None:
    """Reject a Judge that shares provider, model, or API key with the Agent."""
    if judge.provider.casefold() == agent.provider.casefold():
        raise ValueError("Judge provider must differ from Agent provider")
    if judge.model.casefold() == agent.model.casefold():
        raise ValueError("Judge model must differ from Agent model")
    if judge.api_key == agent.api_key:
        raise ValueError("Judge API key must differ from Agent API key")


def _resolve_judge_config(settings: Settings) -> LLMConfig:
    """Resolve the isolated Judge configuration without Agent fallback."""
    raw_provider, api_key, model = _required_judge_values(settings)
    provider = _PROVIDER_ALIASES.get(raw_provider.lower(), raw_provider.lower())
    base_url = settings.judge_api_base or _provider_base_urls(settings).get(provider, "")
    base_url = base_url.strip().rstrip("/")
    if not base_url:
        raise ValueError("JUDGE_API_BASE is required for an unknown Judge provider")
    judge = LLMConfig(
        provider=provider,
        protocol=_resolve_judge_protocol(settings, provider),
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=0.0,
    )
    _validate_judge_isolation(_resolve_llm_config(settings), judge)
    return judge


def _resolve_llm_config(settings: Settings, role: str | None = None) -> LLMConfig:
    """Resolve provider config with generic overrides or isolated Judge settings."""
    if role == "judge":
        return _resolve_judge_config(settings)
    provider = _resolve_provider(settings)
    base_url = _resolve_base_url(settings, provider)
    api_key = _resolve_api_key(settings, provider)

    if not base_url:
        raise ValueError(
            f"LLM_PROVIDER='{provider}' has no built-in API base. "
            f"Set LLM_API_BASE in .env (known presets: {', '.join(sorted(_DEFAULT_MODELS))})."
        )
    if not api_key:
        if not _is_local_endpoint(base_url):
            raise ValueError(
                f"Missing API key for LLM_PROVIDER='{provider}'. "
                f"Set LLM_API_KEY (or {provider.upper()}_API_KEY) in .env."
            )
        api_key = _NO_KEY_PLACEHOLDER

    return LLMConfig(
        provider=provider,
        protocol=_resolve_protocol(settings, provider),
        api_key=api_key,
        base_url=base_url,
        model=_resolve_model(settings, provider, role),
        temperature=settings.llm_temperature,
    )


def _build_openai_client(config: LLMConfig) -> BaseChatModel:
    """Client for OpenAI and every OpenAI-compatible endpoint."""
    return ChatOpenAI(
        model=config.model,
        api_key=config.api_key,  # type: ignore[arg-type]
        base_url=config.base_url,
        temperature=config.temperature,
    )


def _build_anthropic_client(config: LLMConfig) -> BaseChatModel:
    """Client for the native Anthropic Messages API (optional dependency)."""
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError as exc:  # pragma: no cover - depends on local install
        raise ValueError(
            "LLM_PROTOCOL='anthropic' requires the langchain-anthropic package. "
            "Install it with: pip install langchain-anthropic"
        ) from exc

    return ChatAnthropic(
        model=config.model,  # type: ignore[call-arg]
        api_key=config.api_key,  # type: ignore[arg-type]
        base_url=config.base_url,
        temperature=config.temperature,
    )


# Protocol -> client factory. Add an entry here to support a new wire protocol.
_CLIENT_BUILDERS: dict[str, Callable[[LLMConfig], BaseChatModel]] = {
    "openai": _build_openai_client,
    "anthropic": _build_anthropic_client,
}

# Cached clients keyed by resolved config, so repeated node calls reuse one client
_client_cache: dict[LLMConfig, BaseChatModel] = {}
_env_mtime: float | None = None


def reload_llm_config() -> None:
    """Drop cached Settings and LLM clients so .env is re-read on next get_llm()."""
    global _env_mtime
    reload_settings()
    _client_cache.clear()
    _env_mtime = None


def _env_file_changed() -> bool:
    """True when .env mtime changed since the last check (False on first call)."""
    global _env_mtime
    try:
        mtime = _ENV_FILE.stat().st_mtime
    except OSError:
        return False
    changed = _env_mtime is not None and mtime != _env_mtime
    _env_mtime = mtime
    return changed


def _settings_with_hot_reload() -> Settings:
    """Re-read .env when it changes on disk — development only."""
    settings = get_settings()
    if settings.app_env != "development" or not _env_file_changed():
        return settings
    logger.info("Detected .env change — reloading LLM settings")
    reload_settings()
    _client_cache.clear()
    return get_settings()


def get_llm(role: str | None = None) -> BaseChatModel:
    """Return a chat model client for the given role, reusing cached clients.

    Args:
        role: Optional call-site role. "enrich" and "metric" select their
            model override; "judge" uses the isolated Judge configuration.
            None uses the global Agent model configuration.
    """
    settings = _settings_with_hot_reload()
    config = _resolve_llm_config(settings, role=role)

    cached = _client_cache.get(config)
    if cached is not None:
        return cached

    logger.info(
        "Instantiating LLM client (provider=%s, protocol=%s, model=%s, base_url=%s, api_key_set=%s, role=%s)",
        config.provider,
        config.protocol,
        config.model,
        config.base_url,
        config.api_key != _NO_KEY_PLACEHOLDER,
        role or "-",
    )

    client = _CLIENT_BUILDERS[config.protocol](config)
    _client_cache[config] = client
    return client
