from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    openai_whisper_api_key: str = ""

    log_level: str = "INFO"
    database_url: str = "sqlite:///./data/database/agent.db"
    artifacts_dir: str = "./data/artifacts"
    inbox_dir: str = "./data/inbox"
    default_llm_provider: str = "mock"
    default_transcription_provider: str = "mock"
    approval_required_default: bool = True
    app_env: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
