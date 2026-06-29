import os

import pytest


@pytest.fixture(autouse=True)
def clear_settings():
    from operation_drake.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_run_check_passes_with_mock_provider(tmp_path):
    db_dir = tmp_path / "database"
    db_dir.mkdir()
    art_dir = tmp_path / "artifacts"
    art_dir.mkdir()
    os.environ["DATABASE_URL"] = f"sqlite:///{db_dir}/agent.db"
    os.environ["ARTIFACTS_DIR"] = str(art_dir)
    os.environ["DEFAULT_LLM_PROVIDER"] = "mock"
    os.environ["DEFAULT_TRANSCRIPTION_PROVIDER"] = "mock"
    from operation_drake.config import get_settings

    get_settings.cache_clear()
    from operation_drake.main import run_check

    result = run_check()
    assert result == 0


def test_run_check_fails_when_db_dir_missing(tmp_path):
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/nonexistent_dir/agent.db"
    os.environ["DEFAULT_LLM_PROVIDER"] = "mock"
    os.environ["DEFAULT_TRANSCRIPTION_PROVIDER"] = "mock"
    from operation_drake.config import get_settings

    get_settings.cache_clear()
    from operation_drake.main import run_check

    result = run_check()
    assert result == 1


def test_run_check_fails_when_anthropic_key_missing(tmp_path):
    db_dir = tmp_path / "database"
    db_dir.mkdir()
    art_dir = tmp_path / "artifacts"
    art_dir.mkdir()
    os.environ["DATABASE_URL"] = f"sqlite:///{db_dir}/agent.db"
    os.environ["ARTIFACTS_DIR"] = str(art_dir)
    os.environ["DEFAULT_LLM_PROVIDER"] = "anthropic"
    os.environ["ANTHROPIC_API_KEY"] = ""
    from operation_drake.config import get_settings

    get_settings.cache_clear()
    from operation_drake.main import run_check

    result = run_check()
    assert result == 1
