"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore unknown env vars (e.g. typos like ATE_LIMIT_PER_MINUTE)
    )

    weatherstack_api_key: str
    weatherstack_base_url: str = "https://api.weatherstack.com"
    weatherstack_request_timeout: float = 10.0
    cache_ttl_seconds: int = 600
    rate_limit_per_minute: int = 2
    retry_max_retries: int = 3  # 1 initial + 3 retries = 4 total attempts
    retry_initial_delay: float = 0.5


def get_settings() -> Settings:
    """Return validated settings instance."""
    return Settings()


settings = get_settings()
