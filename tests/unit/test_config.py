from operation_drake.config import get_settings


def test_settings_has_required_fields():
    s = get_settings()
    assert s.database_url
    assert s.artifacts_dir
    assert s.default_llm_provider in ("mock", "anthropic", "openai")
    assert s.default_transcription_provider in ("mock", "openai_whisper")
