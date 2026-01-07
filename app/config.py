"""
Application configuration using pydantic-settings.

Loads environment variables from .env file and provides typed access
to configuration values throughout the application.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # API Keys
    anthropic_api_key: str
    patma_api_key: str

    # Claude configuration
    claude_model: str = "claude-sonnet-4-20250514"
    claude_max_tokens: int = 1024

    # Patma API configuration
    patma_base_url: str = "https://app.patma.co.uk/api"

    # Application settings
    debug: bool = False
    app_name: str = "Property Search API"
    app_version: str = "0.1.0"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Using lru_cache ensures we only load settings once and reuse
    the same instance throughout the application lifecycle.
    """
    return Settings()
