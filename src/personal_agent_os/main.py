import argparse

import uvicorn
from fastapi import FastAPI

from personal_agent_os.api.health import router as health_router
from personal_agent_os.api.tasks import router as tasks_router
from personal_agent_os.observability.logging import get_logger
from personal_agent_os.storage.database import init_db

logger = get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="Operation Drake", version="0.1.0", description="Personal AI Agent OS")
    app.include_router(health_router)
    app.include_router(tasks_router)

    @app.on_event("startup")
    def startup() -> None:
        init_db()
        logger.info({"action": "startup", "service": "operation-drake"})

    return app


app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="Operation Drake — Personal AI Agent OS")
    parser.add_argument("--channel", choices=["telegram", "cli", "api"], default="api")
    args = parser.parse_args()

    init_db()

    if args.channel == "telegram":
        from personal_agent_os.channels.telegram import TelegramAdapter
        TelegramAdapter().run()
    elif args.channel == "cli":
        from personal_agent_os.channels.cli import CLIAdapter
        from personal_agent_os.config import get_settings
        CLIAdapter(artifacts_dir=get_settings().artifacts_dir).run_interactive()
    else:
        uvicorn.run("personal_agent_os.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
