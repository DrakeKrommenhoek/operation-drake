import argparse
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from operation_drake.api.health import router as health_router
from operation_drake.api.tasks import router as tasks_router
from operation_drake.config import APP_NAME, APP_VERSION, get_settings
from operation_drake.observability.logging import get_logger
from operation_drake.storage.database import init_db

logger = get_logger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):  # noqa: ARG001
    init_db()
    logger.info({"action": "startup", "service": "operation-drake", "version": APP_VERSION})
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description="Digital Router for Actions, Knowledge, and Execution",
        lifespan=_lifespan,
    )
    app.include_router(health_router)
    app.include_router(tasks_router)
    return app


app = create_app()


def run_check() -> int:
    """Print a diagnostic table. Returns 0 if all required components are present."""
    settings = get_settings()
    issues: list[str] = []
    rows: list[tuple[str, str]] = []

    db_path = settings.database_url.replace("sqlite:///", "")
    db_dir = Path(db_path).parent
    db_ok = db_dir.exists()
    rows.append(("Database directory", "OK" if db_ok else "FAIL -- run mkdir -p data/database"))
    if not db_ok:
        issues.append("database directory missing")

    art_ok = Path(settings.artifacts_dir).exists()
    rows.append(("Artifacts directory", "OK" if art_ok else "FAIL -- run mkdir -p data/artifacts"))
    if not art_ok:
        issues.append("artifacts directory missing")

    provider = settings.default_llm_provider
    if provider == "anthropic":
        key_present = bool(settings.anthropic_api_key)
    elif provider == "openai":
        key_present = bool(settings.openai_api_key)
    else:
        key_present = True
    rows.append(("LLM provider", provider))
    rows.append(
        ("LLM credential", "present" if key_present else f"FAIL -- set API key for {provider}")
    )
    if not key_present:
        issues.append(f"{provider} API key missing")

    t_provider = settings.default_transcription_provider
    if t_provider == "openai_whisper":
        t_key = bool(settings.openai_whisper_api_key or settings.openai_api_key)
    else:
        t_key = True
    rows.append(("Transcription provider", t_provider))
    rows.append(
        ("Transcription credential", "present" if t_key else "FAIL -- set OPENAI_WHISPER_API_KEY")
    )
    if not t_key:
        issues.append("transcription API key missing")

    tg_configured = bool(settings.telegram_bot_token)
    rows.append(
        ("Telegram token", "configured" if tg_configured else "not set (Telegram mode disabled)")
    )

    allowed = settings.allowed_user_ids()
    rows.append(
        (
            "Telegram allowed users",
            f"{len(allowed)} user(s)" if allowed else "WARN -- not set, bot responds to everyone",
        )
    )

    rows.append(("App version", APP_VERSION))

    col_width = max(len(r[0]) for r in rows) + 2
    width = col_width + 40
    print(f"\n  {APP_NAME} -- Diagnostic Check")
    print("-" * width)
    for label, value in rows:
        print(f"  {label:<{col_width}}{value}")
    print("-" * width)

    if issues:
        print(f"\n  FAIL: {len(issues)} issue(s):")
        for issue in issues:
            print(f"    - {issue}")
        return 1

    print("\n  All checks passed.\n")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} -- Digital Router for Actions, Knowledge, and Execution"
    )
    parser.add_argument("--channel", choices=["telegram", "cli", "api"], default="api")
    parser.add_argument("--check", action="store_true", help="Run diagnostic checks and exit")
    args = parser.parse_args()

    if args.check:
        sys.exit(run_check())

    init_db()

    if args.channel == "telegram":
        from operation_drake.channels.telegram import TelegramAdapter

        TelegramAdapter().run()
    elif args.channel == "cli":
        from operation_drake.channels.cli import CLIAdapter

        CLIAdapter(artifacts_dir=get_settings().artifacts_dir).run_interactive()
    else:
        uvicorn.run("operation_drake.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
