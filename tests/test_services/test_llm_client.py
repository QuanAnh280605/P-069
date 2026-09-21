"""Tests for LLM client caching, hot reload, and the protocol factory."""

import pytest
from langchain_openai import ChatOpenAI

from src.config import Settings
from src.services import llm as llm_module

_BASE_FIELDS: dict[str, str] = {
    "app_env": "development",
    "llm_provider": "groq",
    "llm_protocol": "",
    "llm_api_base": "",
    "llm_api_key": "",
    "llm_model": "",
    "llm_model_enrich": "",
    "llm_model_metric": "",
    "groq_api_key": "gsk_test",
    "openai_api_key": "",
    "anthropic_api_key": "",
    "model_name": "llama-3.3-70b-versatile",
}


def _patch_settings(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> Settings:
    """Force llm.get_settings() to return a fixed, .env-independent Settings."""
    settings = Settings(_env_file=None, **{**_BASE_FIELDS, **overrides})
    monkeypatch.setattr(llm_module, "get_settings", lambda: settings)
    return settings


@pytest.fixture(autouse=True)
def _clear_client_cache():
    llm_module._client_cache.clear()
    yield
    llm_module._client_cache.clear()


def test_client_is_cached_per_config(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch)
    first = llm_module.get_llm(role="enrich")
    second = llm_module.get_llm(role="enrich")
    assert first is second
    assert len(llm_module._client_cache) == 1


def test_different_role_model_gives_different_client(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, llm_model_metric="llama-3.1-8b-instant")
    enrich = llm_module.get_llm(role="enrich")
    metric = llm_module.get_llm(role="metric")
    assert enrich is not metric
    assert len(llm_module._client_cache) == 2


def test_same_model_across_roles_reuses_one_client(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch)  # no per-role override -> identical config
    assert llm_module.get_llm(role="enrich") is llm_module.get_llm(role="metric")
    assert len(llm_module._client_cache) == 1


def test_reload_llm_config_drops_cached_client(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch)
    first = llm_module.get_llm(role="enrich")
    llm_module.reload_llm_config()
    _patch_settings(monkeypatch)
    assert llm_module.get_llm(role="enrich") is not first


def test_openai_protocol_builds_chat_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch)
    client = llm_module.get_llm()
    assert isinstance(client, ChatOpenAI)
    assert client.model_name == "llama-3.3-70b-versatile"
    assert client.temperature == 0.0


def test_openrouter_client_disables_reasoning(monkeypatch: pytest.MonkeyPatch) -> None:
    """OpenRouter clients must not spend latency on unnecessary reasoning tokens."""
    _patch_settings(
        monkeypatch,
        llm_provider="openai",
        llm_api_base="https://openrouter.ai/api/v1",
        llm_api_key="sk-or-test",
        llm_model="deepseek/deepseek-v4-flash-0731",
    )

    client = llm_module.get_llm(role="metric")

    assert client.extra_body == {"reasoning": {"enabled": False}}


def test_openrouter_client_preserves_reasoning_for_gemini_and_glm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reasoning-native models reject reasoning: {enabled: false} on OpenRouter with HTTP 400."""
    _patch_settings(
        monkeypatch,
        llm_provider="openai",
        llm_api_base="https://openrouter.ai/api/v1",
        llm_api_key="sk-or-test",
        llm_model="google/gemini-3.8-flash",
        llm_fallback_model="z-ai/glm-5.3-flash",
    )

    client = llm_module.get_llm(role="metric")
    primary = getattr(client, "first", client)
    assert primary.extra_body == {"models": ["google/gemini-3.8-flash", "z-ai/glm-5.3-flash"]}


def test_anthropic_protocol_builds_anthropic_client(monkeypatch: pytest.MonkeyPatch) -> None:
    chat_anthropic = pytest.importorskip("langchain_anthropic").ChatAnthropic
    _patch_settings(
        monkeypatch,
        llm_provider="anthropic",
        anthropic_api_key="sk-ant-test",
        model_name="claude-sonnet-5",
    )
    client = llm_module.get_llm(role="enrich")
    assert isinstance(client, chat_anthropic)
    assert client.model == "claude-sonnet-5"


def test_env_file_change_is_ignored_outside_development(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch, app_env="production")
    monkeypatch.setattr(llm_module, "_env_file_changed", lambda: pytest.fail("must not stat .env in prod"))
    assert llm_module.get_llm() is not None


def test_fallback_model_builds_runnable_with_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    from langchain_core.runnables import RunnableWithFallbacks

    _patch_settings(monkeypatch, llm_fallback_model="z-ai/glm-5.3-flash")
    client = llm_module.get_llm()
    assert isinstance(client, RunnableWithFallbacks)

