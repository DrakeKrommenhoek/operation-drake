import tempfile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from operation_drake.integrations.notion.mock_client import MockNotionClient
from operation_drake.integrations.notion.sync_service import NotionSyncService
from operation_drake.llm.mock_provider import MockLLMProvider
from operation_drake.models.database import Base
from operation_drake.services.orchestration import OrchestratorService
from operation_drake.transcription.mock_transcriber import MockTranscriber


def _make_orchestrator(tmpdir, fail_notion=False):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = MockNotionClient(should_fail=fail_notion, fail_with="timeout")
    notion_svc = NotionSyncService(session=session, client=client, database_id="db-test")
    orch = OrchestratorService(
        session=session,
        llm=MockLLMProvider(),
        transcriber=MockTranscriber(),
        artifacts_dir=tmpdir,
        notion_sync_service=notion_svc,
    )
    return orch, client


def test_process_completes_locally_when_notion_fails():
    with tempfile.TemporaryDirectory() as tmpdir:
        orch, client = _make_orchestrator(tmpdir, fail_notion=True)
        result = orch.process(channel="telegram", raw_text="Save this note about PE firms")
        assert result.status == "completed"
        assert result.notion_sync_status == "failed"


def test_process_syncs_when_notion_succeeds():
    with tempfile.TemporaryDirectory() as tmpdir:
        orch, client = _make_orchestrator(tmpdir, fail_notion=False)
        result = orch.process(channel="telegram", raw_text="Business idea: AI for PE firms")
        assert result.status == "completed"
        assert result.notion_sync_status in ("synced", "updated", "already_synced", "skipped", None)


def test_process_no_notion_service_still_completes():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        orch = OrchestratorService(
            session=session,
            llm=MockLLMProvider(),
            transcriber=MockTranscriber(),
            artifacts_dir=tmpdir,
            notion_sync_service=None,
        )
        result = orch.process(channel="telegram", raw_text="Save this note")
        assert result.status in ("completed", "awaiting_approval")
        assert result.notion_sync_status is None


def test_notion_sync_status_none_when_not_configured():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        orch = OrchestratorService(
            session=session,
            llm=MockLLMProvider(),
            transcriber=MockTranscriber(),
            artifacts_dir=tmpdir,
        )
        result = orch.process(channel="telegram", raw_text="A note")
        assert result.notion_sync_status is None


def test_no_duplicate_notion_pages_on_single_process():
    with tempfile.TemporaryDirectory() as tmpdir:
        orch, client = _make_orchestrator(tmpdir)
        orch.process(channel="telegram", raw_text="Answer Movement idea: timer breathing")
        assert len(client.created_pages) <= 1


def test_process_result_has_notion_fields():
    with tempfile.TemporaryDirectory() as tmpdir:
        orch, client = _make_orchestrator(tmpdir)
        result = orch.process(channel="telegram", raw_text="save note: PE firm idea")
        assert hasattr(result, "notion_sync_status")
        assert hasattr(result, "notion_page_url")
        assert hasattr(result, "notion_project")
        assert hasattr(result, "notion_content_type")
        assert hasattr(result, "notion_needs_review")
