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

    # LLM
    openai_api_key: str = ""
    model_name: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)  # 0.0 for deterministic output

    # SQL dump scanner (release-tested hard maxima)
    sql_dump_max_file_bytes: int = Field(default=20 * 1024 * 1024, gt=0, le=20 * 1024 * 1024)
    sql_dump_max_statement_bytes: int = Field(default=1024 * 1024, gt=0, le=1024 * 1024)
    sql_dump_max_diagnostics: int = Field(default=100, ge=1, le=1000)
    sql_dump_max_nesting_depth: int = Field(default=128, ge=1, le=512)
    sql_dump_chunk_bytes: int = Field(default=64 * 1024, ge=1024, le=256 * 1024)

    # Experimental SQL dump preview (always disabled in production)
    sql_dump_preview_enabled: bool = True
    sql_dump_preview_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    sql_dump_preview_max_drafts: int = Field(default=500, ge=1, le=5000)

    # Metadata Store (PostgreSQL dev/prod, no SQLite)
    database_url: str = "postgresql+asyncpg://dev:devpassword@localhost:5432/semantic_layer_dev"
    encryption_key: str = ""  # Base64 Fernet key — must be set via .env


@lru_cache
def get_settings() -> Settings:
    return Settings()
