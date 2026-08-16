from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "AI Semantic Layer Agent"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:3000"
    secret_key: str = "dev-secret-key-change-in-prod-semantic-layer-2026"

    # LLM Provider — any OpenAI-compatible endpoint name is accepted.
    # Known presets: openai | gemini | groq | mimo | anthropic.
    # Aliases: google -> gemini, claude -> anthropic.
    # A custom name (e.g. "custom", "vllm", "deepseek") requires LLM_API_BASE below.
    llm_provider: str = "mimo"

    # Wire protocol used to talk to the provider. Empty = derive from LLM_PROVIDER
    # (everything OpenAI-compatible -> "openai", anthropic -> "anthropic").
    llm_protocol: str = ""  # openai | anthropic

    # LLM generic override — highest priority, wins over every per-provider value below.
    # Leave empty to fall back to the LLM_PROVIDER preset.
    llm_api_base: str = ""  # LLM_API_BASE
    llm_api_key: str = ""  # LLM_API_KEY
    llm_model: str = ""  # LLM_MODEL

    # Per-role model override (empty = use LLM_MODEL / MODEL_NAME for every role)
    llm_model_enrich: str = ""  # LLM_MODEL_ENRICH — schema enrichment nodes
    llm_model_metric: str = ""  # LLM_MODEL_METRIC — metric suggestion nodes

    # LLM per-provider keys (used when LLM_API_KEY is empty)
    openai_api_key: str = ""
    groq_api_key: str = ""
    mimo_api_key: str = ""
    google_api_key: str = ""
    anthropic_api_key: str = ""
    model_name: str = ""  # empty -> per-provider default in services/llm.py
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)  # 0.0 for deterministic output

    # AI Judge identity is mandatory and isolated when role="judge" is requested.
    judge_llm_provider: str = ""
    judge_llm_protocol: str = ""
    judge_api_key: str = ""
    judge_model_name: str = ""
    judge_api_base: str = ""

    # LLM per-provider base URLs (used when LLM_API_BASE is empty)
    openai_api_base: str = "https://api.openai.com/v1"
    mimo_api_base: str = "https://api.xiaomimimo.com/v1"
    groq_api_base: str = "https://api.groq.com/openai/v1"
    google_api_base: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    anthropic_api_base: str = "https://api.anthropic.com"

    # SQL dump parsing limits
    sql_dump_max_file_bytes: int = Field(default=20 * 1024 * 1024, gt=0, le=20 * 1024 * 1024)
    sql_dump_max_statement_bytes: int = Field(default=1024 * 1024, gt=0, le=1024 * 1024)
    sql_dump_max_diagnostics: int = Field(default=100, ge=1, le=1000)
    sql_dump_max_nesting_depth: int = Field(default=128, ge=1, le=512)

    # Metadata Store (PostgreSQL dev/prod, no SQLite)
    database_url: str = "postgresql+asyncpg://dev:devpassword@localhost:5432/semantic_layer_dev"
    encryption_key: str = ""  # Base64 Fernet key — must be set via .env


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    """Drop the cached Settings so .env is re-read (dev hot-reload, tests)."""
    get_settings.cache_clear()
    return get_settings()
