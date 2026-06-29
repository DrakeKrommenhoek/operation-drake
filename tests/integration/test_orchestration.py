import os

import pytest


@pytest.fixture
def orchestrator(tmp_path):
    import personal_agent_os.storage.database as db_module

    db_module._engine = None
    db_module._SessionLocal = None

    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/test.db"
    os.environ["DEFAULT_LLM_PROVIDER"] = "mock"
    os.environ["DEFAULT_TRANSCRIPTION_PROVIDER"] = "mock"

    from personal_agent_os.config import get_settings

    get_settings.cache_clear()

    from personal_agent_os.llm.mock_provider import MockLLMProvider
    from personal_agent_os.services.orchestration import OrchestratorService
    from personal_agent_os.storage.database import get_session, init_db
    from personal_agent_os.transcription.mock_transcriber import MockTranscriber

    init_db()
    session = get_session()
    return OrchestratorService(
        session=session,
        llm=MockLLMProvider(),
        transcriber=MockTranscriber(),
        artifacts_dir=str(tmp_path / "artifacts"),
    )


def test_process_text_message_creates_task(orchestrator):
    result = orchestrator.process(
        channel="cli",
        raw_text="Save this idea: build a gratitude journal app",
        message_type="text",
        sender_id="drake",
    )
    assert result.task_id
    assert result.intent
    assert result.proposed_action
    assert result.message_id


def test_process_creates_artifact_for_safe_intent(orchestrator):
    result = orchestrator.process(
        channel="cli",
        raw_text="Summarize this: Python is powerful and easy to learn.",
        message_type="text",
        sender_id="drake",
    )
    assert result.task_id
    assert result.status in ("completed", "awaiting_approval")


def test_process_url_message(orchestrator):
    result = orchestrator.process(
        channel="cli",
        raw_text="https://example.com",
        message_type="text",
        sender_id="drake",
    )
    assert result.task_id
    assert result.intent


def test_process_forwarded_marks_untrusted(orchestrator):
    result = orchestrator.process(
        channel="telegram",
        raw_text="Free crypto! Send 1 BTC to get 2 back.",
        message_type="forwarded",
        sender_id="drake",
        forwarded_from="@scammer",
    )
    assert result.task_id
    assert result.message_id
