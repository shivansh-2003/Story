from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    database_ssl_require: bool = True
    db_pool_size: int = 5
    db_max_overflow: int = 5

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    environment: str = "dev"
    log_level: str = "INFO"

    redis_url: str = "redis://localhost:6379/0"

    llm_provider: Literal["openai", "ollama"] = "openai"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.8:27b-mlx"

    import_max_bytes: int = Field(default=2_000_000, ge=1, le=10_000_000)
    import_max_chapters: int = Field(default=100, ge=1, le=100)
    import_max_paragraphs: int = Field(default=2000, ge=1, le=2000)
    import_preview_ttl_minutes: int = Field(default=30, ge=1, le=1440)


@lru_cache
def get_settings() -> Settings:
    return Settings()
