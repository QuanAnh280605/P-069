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

    # LLM Provider & Keys
    llm_provider: str = "mimo"  # openai | gemini | groq | mimo
    openai_api_key: str = ""
    groq_api_key: str = ""
    mimo_api_key: str = ""
    google_api_key: str = ""
    model_name: str = "mimo-v2.5"
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)  # 0.0 for deterministic output

    # LLM Base URLs — configurable via .env, defaults to official endpoints
    openai_api_base: str = "https://api.openai.com/v1"
    mimo_api_base: str = "https://api.xiaomimimo.com/v1"
    groq_api_base: str = "https://api.groq.com/openai/v1"
    google_api_base: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

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
