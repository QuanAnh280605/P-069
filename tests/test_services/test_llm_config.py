"""Tests for LLM provider config resolution (generic LLM_* overrides + presets)."""

import pytest

from src.config import Settings
from src.services.llm import _DEFAULT_MODELS, _resolve_llm_config

# LLM fields forced to empty so .env / os.environ never leaks into assertions.
# Init kwargs have the highest priority in pydantic-settings.
_ISOLATED_LLM_FIELDS: dict[str, str] = {
    "llm_provider": "openai",
    "llm_protocol": "",
    "llm_api_base": "",
    "llm_api_key": "",
    "llm_model": "",
    "llm_model_enrich": "",
    "llm_model_metric": "",
    "openai_api_key": "",
    "groq_api_key": "",
    "mimo_api_key": "",
    "google_api_key": "",
    "anthropic_api_key": "",
    "model_name": "",
}


def _settings(**overrides: str) -> Settings:
    """Build Settings isolated from .env for every LLM-related field."""
    return Settings(_env_file=None, **{**_ISOLATED_LLM_FIELDS, **overrides})


def test_preset_provider_uses_builtin_base_and_key() -> None:
    config = _resolve_llm_config(
        _settings(
            llm_provider="groq",
            groq_api_key="gsk_test",
            model_name="llama-3.3-70b-versatile",
        )
    )
    assert config.provider == "groq"
    assert config.api_key == "gsk_test"
    assert config.base_url == "https://api.groq.com/openai/v1"
    assert config.model == "llama-3.3-70b-versatile"


def test_generic_overrides_win_over_provider_fields() -> None:
    config = _resolve_llm_config(
        _settings(
            llm_provider="openai",
            openai_api_key="sk-preset",
            model_name="gpt-4o-mini",
            llm_api_base="https://llm-proxy.internal/v1",
            llm_api_key="sk-override",
            llm_model="gpt-4.1",
        )
    )
    assert config.base_url == "https://llm-proxy.internal/v1"
    assert config.api_key == "sk-override"
    assert config.model == "gpt-4.1"


def test_custom_provider_works_without_code_change() -> None:
    config = _resolve_llm_config(
        _settings(
            llm_provider="deepseek",
            llm_api_base="https://api.deepseek.com/v1/",
            llm_api_key="sk-deepseek",
            llm_model="deepseek-chat",
        )
    )
    assert config.provider == "deepseek"
    assert config.base_url == "https://api.deepseek.com/v1"  # trailing slash normalized
    assert config.api_key == "sk-deepseek"
    assert config.model == "deepseek-chat"


def test_unknown_provider_without_base_raises() -> None:
    with pytest.raises(ValueError, match="LLM_API_BASE"):
        _resolve_llm_config(_settings(llm_provider="vllm", llm_api_key="sk-x"))


def test_local_endpoint_allows_missing_api_key() -> None:
    config = _resolve_llm_config(
        _settings(
            llm_provider="custom",
            llm_api_base="http://localhost:8000/v1",
            llm_model="qwen2.5-32b-instruct",
        )
    )
    assert config.api_key == "not-needed"
    assert config.base_url == "http://localhost:8000/v1"


def test_remote_endpoint_without_api_key_raises() -> None:
    with pytest.raises(ValueError, match="MIMO_API_KEY"):
        _resolve_llm_config(_settings(llm_provider="mimo"))


def test_empty_model_falls_back_to_provider_default() -> None:
    config = _resolve_llm_config(_settings(llm_provider="groq", groq_api_key="gsk_test"))
    assert config.model == _DEFAULT_MODELS["groq"]


def test_openai_api_key_is_last_resort_for_preset_provider() -> None:
    config = _resolve_llm_config(_settings(llm_provider="gemini", openai_api_key="sk-shared"))
    assert config.api_key == "sk-shared"
    assert config.base_url == "https://generativelanguage.googleapis.com/v1beta/openai"


# --- provider aliases -------------------------------------------------------


def test_google_alias_resolves_to_gemini() -> None:
    config = _resolve_llm_config(_settings(llm_provider="google", google_api_key="AIza-test"))
    assert config.provider == "gemini"
    assert config.base_url == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert config.api_key == "AIza-test"


def test_claude_alias_resolves_to_anthropic() -> None:
    config = _resolve_llm_config(_settings(llm_provider="claude", anthropic_api_key="sk-ant-test"))
    assert config.provider == "anthropic"
    assert config.protocol == "anthropic"
    assert config.model == _DEFAULT_MODELS["anthropic"]


# --- wire protocol ----------------------------------------------------------


def test_openai_compatible_provider_uses_openai_protocol() -> None:
    config = _resolve_llm_config(_settings(llm_provider="groq", groq_api_key="gsk_test"))
    assert config.protocol == "openai"


def test_llm_protocol_overrides_provider_inference() -> None:
    config = _resolve_llm_config(
        _settings(
            llm_provider="my-claude-proxy",
            llm_protocol="anthropic",
            llm_api_base="https://proxy.internal",
            llm_api_key="sk-ant-proxy",
            llm_model="claude-sonnet-5",
        )
    )
    assert config.protocol == "anthropic"
    assert config.provider == "my-claude-proxy"


def test_unsupported_protocol_raises() -> None:
    with pytest.raises(ValueError, match="LLM_PROTOCOL"):
        _resolve_llm_config(_settings(llm_provider="openai", openai_api_key="sk-x", llm_protocol="bedrock"))


# --- per-role model override ------------------------------------------------


def test_role_model_override_applies_only_to_that_role() -> None:
    settings = _settings(
        llm_provider="groq",
        groq_api_key="gsk_test",
        model_name="llama-3.3-70b-versatile",
        llm_model_enrich="llama-3.1-8b-instant",
    )
    assert _resolve_llm_config(settings, role="enrich").model == "llama-3.1-8b-instant"
    assert _resolve_llm_config(settings, role="metric").model == "llama-3.3-70b-versatile"
    assert _resolve_llm_config(settings).model == "llama-3.3-70b-versatile"


def test_unknown_role_raises() -> None:
    with pytest.raises(ValueError, match="Unknown LLM role"):
        _resolve_llm_config(_settings(llm_provider="groq", groq_api_key="gsk_test"), role="typo")


def test_temperature_is_part_of_resolved_config() -> None:
    config = _resolve_llm_config(_settings(llm_provider="groq", groq_api_key="gsk_test"))
    assert config.temperature == 0.0


def test_metric_generation_limits_have_safe_defaults() -> None:
    settings = _settings()
    assert settings.llm_metric_timeout_seconds == 0.0
    assert settings.llm_metric_max_output_tokens == 1200


def test_fallback_model_is_part_of_resolved_config() -> None:
    config = _resolve_llm_config(
        _settings(llm_provider="groq", groq_api_key="gsk_test", llm_fallback_model="z-ai/glm-5.3-flash")
    )
    assert config.fallback_model == "z-ai/glm-5.3-flash"


