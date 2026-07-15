"""Minimal stdlib .env loader for health/.

Deliberately does not import operation_drake.config -- health/ must not depend on
the bot's package. Reads health/.env directly.
"""

from __future__ import annotations

import os
from pathlib import Path

HEALTH_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        os.environ.setdefault(key, value)


_load_dotenv(HEALTH_DIR / ".env")


class Settings:
    def __init__(self) -> None:
        self.client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
        self.client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
        self.redirect_uri = os.environ.get(
            "GOOGLE_OAUTH_REDIRECT_URI", "http://127.0.0.1:3000/callback"
        )
        self.db_path = self._resolve(os.environ.get("HEALTH_DB_PATH", "../data/database/agent.db"))
        self.token_path = self._resolve(os.environ.get("HEALTH_TOKEN_PATH", "./.token.json"))

    @staticmethod
    def _resolve(raw: str) -> Path:
        path = Path(raw)
        if not path.is_absolute():
            path = (HEALTH_DIR / path).resolve()
        return path


def get_settings() -> Settings:
    return Settings()
