from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_tags_url: str = "http://localhost:11434/api/tags"
    model_name: str = "qwen2.5-coder:7b"
    temperature: float = 0.1
    max_steps: int = 6
    tool_workdir: str = "."
    api_key: str = ""
    request_timeout: int = 60

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
