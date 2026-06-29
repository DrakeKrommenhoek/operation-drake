from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_NAME = "D.R.A.K.E."
APP_VERSION = "0.1.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str = ""
    # Comma-separated Telegram user IDs allowed to interact with the bot.
    # If empty, the bot responds to everyone (not recommended for production).
    telegram_allowed_user_ids: str = ""
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

    def allowed_user_ids(self) -> set[str]:
        """Return the set of allowed Telegram user IDs, or empty set (allow all)."""
        if not self.telegram_allowed_user_ids.strip():
            return set()
        return {uid.strip() for uid in self.telegram_allowed_user_ids.split(",") if uid.strip()}

    def is_user_allowed(self, user_id: str) -> bool:
        """Return True if user_id is allowed, or if no restriction is configured."""
        allowed = self.allowed_user_ids()
        if not allowed:
            return True
        return user_id in allowed


@lru_cache
def get_settings() -> Settings:
    return Settings()
