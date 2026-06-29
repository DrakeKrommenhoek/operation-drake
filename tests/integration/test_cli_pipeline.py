import os

import pytest


@pytest.fixture
def cli_adapter(tmp_path):
    import personal_agent_os.storage.database as db_module

    db_module._engine = None
    db_module._SessionLocal = None

    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/cli_test.db"
    os.environ["DEFAULT_LLM_PROVIDER"] = "mock"
    os.environ["DEFAULT_TRANSCRIPTION_PROVIDER"] = "mock"
    os.environ["ARTIFACTS_DIR"] = str(tmp_path / "artifacts")

    from personal_agent_os.config import get_settings

    get_settings.cache_clear()

    from personal_agent_os.channels.cli import CLIAdapter
    from personal_agent_os.storage.database import init_db

    init_db()
    return CLIAdapter(artifacts_dir=str(tmp_path / "artifacts"))


def test_cli_happy_path(cli_adapter):
    response = cli_adapter.run_once("Save this as a note: I want to build a morning routine tracker")
    assert response
    assert len(response) > 20
    assert "Intent" in response or "intent" in response


def test_cli_returns_status(cli_adapter):
    response = cli_adapter.run_once("Summarize: Python is a high-level language.")
    assert "Status" in response or "status" in response


def test_cli_url_input(cli_adapter):
    response = cli_adapter.run_once("https://example.com")
    assert response


def test_cli_empty_handling(cli_adapter):
    response = cli_adapter.run_once("   ")
    assert isinstance(response, str)
