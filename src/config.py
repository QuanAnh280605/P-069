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
    secret_key: str = "supersecretjwtkey_semantic_agent_2026"

    # LLM
    openai_api_key: str = ""
    model_name: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)  # 0.0 for deterministic output

    # Metadata Store (PostgreSQL dev/prod, no SQLite)
    database_url: str = "postgresql+asyncpg://dev:devpassword@localhost:5432/semantic_layer_dev"
    encryption_key: str = "FiqLMBulPbTUShiUnFKXgt2OHpPv9Y3mBstowcTSKRc="  # Base64 Fernet key


@lru_cache
def get_settings() -> Settings:
    return Settings()
