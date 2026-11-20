"""Runtime settings, read from environment variables (and an optional .env file)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Any pydantic-ai model string, e.g. "deepseek:deepseek-chat",
    # "openai:gpt-4.1-mini", "anthropic:claude-sonnet-5-5".
    # The matching provider key (DEEPSEEK_API_KEY / OPENAI_API_KEY / ...) is read
    # by pydantic-ai itself from the environment.
    llm_model: str = "deepseek:deepseek-chat"

    # How many times pydantic-ai may ask the model to fix an invalid plan.
    llm_output_retries: int = 2

    max_upload_bytes: int = 10 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
