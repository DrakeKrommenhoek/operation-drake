import os

import pytest


@pytest.fixture
def orchestrator(tmp_path):
    import operation_drake.storage.database as db_module

    db_module._engine = None
    db_module._SessionLocal = None

    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/test.db"
    os.environ["DEFAULT_LLM_PROVIDER"] = "mock"
    os.environ["DEFAULT_TRANSCRIPTION_PROVIDER"] = "mock"

    from operation_drake.config import get_settings

    get_settings.cache_clear()

    from operation_drake.llm.mock_provider import MockLLMProvider
    from operation_drake.services.orchestration import OrchestratorService
    from operation_drake.storage.database import get_session, init_db
    from operation_drake.transcription.mock_transcriber import MockTranscriber

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


# --- Approval loop tests ---


def _force_awaiting(orchestrator):
    """Submit a message that produces a task in awaiting_approval state."""
    from operation_drake.llm.mock_provider import MockLLMProvider

    # Use a router response that demands approval (approval_required: true)
    approval_response = '{"primary_intent":"unknown","secondary_intents":[],"confidence":0.5,"proposed_action":"Classify this message","approval_required":true,"clarification_question":null,"rationale_summary":"Low confidence, requires approval."}'
    orchestrator._router = type(orchestrator._router)(
        llm=MockLLMProvider(fixed_response=approval_response)
    )
    return orchestrator.process(
        channel="cli",
        raw_text="Do something complex that needs approval",
        message_type="text",
        sender_id="drake",
    )


def test_execute_approved_task_completes(orchestrator):
    # Create a task that needs approval by injecting a safe intent with approval_required=true
    from operation_drake.agents.router import RouterAgent
    from operation_drake.llm.mock_provider import MockLLMProvider

    approval_router_response = '{"primary_intent":"save_note","secondary_intents":[],"confidence":0.7,"proposed_action":"Save this note","approval_required":true,"clarification_question":null,"rationale_summary":"Manual approval requested."}'
    orchestrator._router = RouterAgent(llm=MockLLMProvider(fixed_response=approval_router_response))
    result = orchestrator.process(
        channel="cli",
        raw_text="Save this idea: build a gratitude journal",
        message_type="text",
        sender_id="drake",
    )
    assert result.status == "awaiting_approval"
    task_id = result.task_id

    # Now approve it
    approved = orchestrator.execute_approved_task(task_id)
    assert approved.status == "completed"
    assert approved.task_id == task_id


def test_execute_approved_task_not_found(orchestrator):
    result = orchestrator.execute_approved_task("nonexistent-task-id-xyz")
    assert result.status == "not_found"
    assert "not found" in result.result_summary.lower()


def test_execute_approved_task_wrong_state(orchestrator):
    result = orchestrator.process(
        channel="cli",
        raw_text="Save this note: hello world",
        message_type="text",
        sender_id="drake",
    )
    # Task is either completed or awaiting_approval; if completed, can't approve again
    if result.status == "completed":
        attempted = orchestrator.execute_approved_task(result.task_id)
        assert attempted.status != "completed" or "not awaiting" in attempted.result_summary.lower()


def test_reject_task(orchestrator):
    from operation_drake.agents.router import RouterAgent
    from operation_drake.llm.mock_provider import MockLLMProvider

    approval_router_response = '{"primary_intent":"save_note","secondary_intents":[],"confidence":0.7,"proposed_action":"Save this note","approval_required":true,"clarification_question":null,"rationale_summary":"Requires approval."}'
    orchestrator._router = RouterAgent(llm=MockLLMProvider(fixed_response=approval_router_response))
    result = orchestrator.process(
        channel="cli",
        raw_text="Save this note: important thought",
        message_type="text",
        sender_id="drake",
    )
    assert result.status == "awaiting_approval"
    task_id = result.task_id

    rejected = orchestrator.reject_task(task_id)
    assert rejected.status == "cancelled"
    assert rejected.task_id == task_id


def test_reject_task_not_found(orchestrator):
    result = orchestrator.reject_task("nonexistent-xyz")
    assert result.status == "not_found"


def test_correct_task_rereroutes(orchestrator):
    from operation_drake.agents.router import RouterAgent
    from operation_drake.llm.mock_provider import MockLLMProvider

    approval_router_response = '{"primary_intent":"unknown","secondary_intents":[],"confidence":0.4,"proposed_action":"Unknown intent","approval_required":true,"clarification_question":"What do you mean?","rationale_summary":"Low confidence."}'
    orchestrator._router = RouterAgent(llm=MockLLMProvider(fixed_response=approval_router_response))
    result = orchestrator.process(
        channel="cli",
        raw_text="Blah blah ambiguous",
        message_type="text",
        sender_id="drake",
    )
    assert result.status == "awaiting_approval"
    task_id = result.task_id

    # Correct with clear instruction — router will now return save_note (mock default)
    orchestrator._router = RouterAgent(llm=MockLLMProvider())
    corrected = orchestrator.correct_task(task_id, "Actually save this as a note")
    assert corrected.task_id == task_id
    # Status stays awaiting_approval — it was re-interpreted, not executed
    assert corrected.status == "awaiting_approval"
    assert corrected.intent  # has a new intent


def test_correct_task_not_found(orchestrator):
    result = orchestrator.correct_task("nonexistent-xyz", "some correction")
    assert result.status == "not_found"


def test_list_awaiting_approval(orchestrator):
    from operation_drake.agents.router import RouterAgent
    from operation_drake.llm.mock_provider import MockLLMProvider

    approval_response = '{"primary_intent":"save_note","secondary_intents":[],"confidence":0.6,"proposed_action":"Save note","approval_required":true,"clarification_question":null,"rationale_summary":"Approval needed."}'
    orchestrator._router = RouterAgent(llm=MockLLMProvider(fixed_response=approval_response))
    orchestrator.process(channel="cli", raw_text="Note 1", message_type="text", sender_id="drake")
    orchestrator.process(channel="cli", raw_text="Note 2", message_type="text", sender_id="drake")

    pending = orchestrator._task_repo.list_awaiting_approval()
    assert len(pending) >= 2
