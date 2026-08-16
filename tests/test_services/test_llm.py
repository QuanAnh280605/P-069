"""Compatibility tests for flexible Agent config and isolated AI Judge config."""

import pytest

from src.config import Settings
from src.services import llm as llm_module
from src.services.llm import _resolve_llm_config

_BASE_FIELDS: dict[str, str] = {
    "app_env": "test",
    "llm_provider": "openai",
    "llm_protocol": "",
    "llm_api_base": "",
    "llm_api_key": "",
    "llm_model": "",
    "llm_model_enrich": "",
    "llm_model_metric": "",
    "openai_api_key": "agent-secret",
    "groq_api_key": "",
    "mimo_api_key": "",
    "google_api_key": "",
    "anthropic_api_key": "",
    "model_name": "gpt-4o-mini",
    "judge_llm_provider": "groq",
    "judge_llm_protocol": "",
    "judge_api_key": "judge-secret",
    "judge_model_name": "llama-3.3-70b-versatile",
    "judge_api_base": "",
}


def _settings(**overrides: str) -> Settings:
    """Build settings isolated from local environment variables."""
    return Settings(_env_file=None, **{**_BASE_FIELDS, **overrides})


def test_agent_generic_overrides_remain_supported() -> None:
    config = _resolve_llm_config(
        _settings(
            llm_provider="deepseek",
            llm_api_base="https://api.deepseek.com/v1/",
            llm_api_key="agent-deepseek-key",
            llm_model="deepseek-chat",
        )
    )
    assert config.provider == "deepseek"
    assert config.base_url == "https://api.deepseek.com/v1"
    assert config.api_key == "agent-deepseek-key"
    assert config.model == "deepseek-chat"


def test_agent_role_model_overrides_remain_supported() -> None:
    settings = _settings(
        llm_model="shared-model",
        llm_model_enrich="enrich-model",
        llm_model_metric="metric-model",
    )
    assert _resolve_llm_config(settings, role="enrich").model == "enrich-model"
    assert _resolve_llm_config(settings, role="metric").model == "metric-model"
    assert _resolve_llm_config(settings).model == "shared-model"


def test_judge_resolution_uses_dedicated_identity() -> None:
    config = _resolve_llm_config(_settings(), role="judge")
    assert config.provider == "groq"
    assert config.api_key == "judge-secret"
    assert config.base_url == "https://api.groq.com/openai/v1"
    assert config.model == "llama-3.3-70b-versatile"
    assert config.temperature == 0.0


@pytest.mark.parametrize(
    ("field", "message"),
    (
        ("judge_llm_provider", "JUDGE_LLM_PROVIDER is required"),
        ("judge_api_key", "JUDGE_API_KEY is required"),
        ("judge_model_name", "JUDGE_MODEL_NAME is required"),
    ),
)
def test_judge_rejects_missing_required_setting(field: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _resolve_llm_config(_settings(**{field: ""}), role="judge")


@pytest.mark.parametrize(
    ("overrides", "message"),
    (
        ({"judge_llm_provider": "OPENAI"}, "provider must differ"),
        ({"judge_model_name": "GPT-4O-MINI"}, "model must differ"),
        ({"judge_api_key": "agent-secret"}, "API key must differ"),
    ),
)
def test_judge_rejects_agent_identity(overrides: dict[str, str], message: str) -> None:
    with pytest.raises(ValueError, match=message) as raised:
        _resolve_llm_config(_settings(**overrides), role="judge")
    assert "agent-secret" not in str(raised.value)
    assert "judge-secret" not in str(raised.value)


def test_unknown_judge_provider_requires_base_url() -> None:
    with pytest.raises(ValueError, match="JUDGE_API_BASE is required"):
        _resolve_llm_config(_settings(judge_llm_provider="custom"), role="judge")


def test_judge_client_uses_shared_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings()
    monkeypatch.setattr(llm_module, "get_settings", lambda: settings)
    llm_module._client_cache.clear()
    first = llm_module.get_llm(role="judge")
    second = llm_module.get_llm(role="judge")
    assert first is second
    assert first.model_name == "llama-3.3-70b-versatile"
    assert len(llm_module._client_cache) == 1
