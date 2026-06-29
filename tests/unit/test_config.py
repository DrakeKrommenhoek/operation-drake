import os

from operation_drake.config import get_settings


def test_settings_has_required_fields():
    s = get_settings()
    assert s.database_url
    assert s.artifacts_dir
    assert s.default_llm_provider in ("mock", "anthropic", "openai")
    assert s.default_transcription_provider in ("mock", "openai_whisper")


def test_init_db_creates_database_directory(tmp_path):
    """init_db must create the database directory if it does not exist."""
    import operation_drake.storage.database as db_module

    db_dir = tmp_path / "nested" / "db"
    db_file = db_dir / "agent.db"
    assert not db_dir.exists()

    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"
    get_settings.cache_clear()
    db_module._engine = None
    db_module._SessionLocal = None

    from operation_drake.storage.database import init_db

    init_db()

    assert db_dir.exists(), "init_db() must create the database directory"
    assert db_file.exists(), "init_db() must create the database file"

    # cleanup
    db_module._engine.dispose()
    db_module._engine = None
    db_module._SessionLocal = None
    del os.environ["DATABASE_URL"]
    get_settings.cache_clear()


def test_ensure_db_dir_noop_for_non_sqlite():
    from operation_drake.storage.database import _ensure_db_dir

    # Must not raise or create anything for non-SQLite URLs
    _ensure_db_dir("postgresql://localhost/mydb")
    _ensure_db_dir("")
