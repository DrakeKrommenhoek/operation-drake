from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from operation_drake.integrations.notion.mock_client import MockNotionClient
from operation_drake.integrations.notion.models import NotionClassification
from operation_drake.integrations.notion.sync_service import NotionSyncService
from operation_drake.models.database import Base


def _make_svc(client=None):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    if client is None:
        client = MockNotionClient()
    return NotionSyncService(session=session, client=client, database_id="db-1")


def _ts():
    return datetime(2026, 7, 4, tzinfo=UTC)


def _clf(title="Test", task_id="t1", sync_to_notion=True, confidence=0.9, notion_status="Inbox"):
    return NotionClassification(
        title=title,
        task_id=task_id,
        sync_to_notion=sync_to_notion,
        confidence=confidence,
        notion_status=notion_status,
        summary="Summary text.",
    )


def test_sync_success_creates_page():
    client = MockNotionClient()
    svc = _make_svc(client)
    result = svc.sync("t1", "a1", _clf(task_id="t1"), _ts())
    assert result.status == "synced"
    assert result.page_id
    assert "notion.so" in result.page_url
    assert len(client.created_pages) == 1


def test_sync_skipped_when_user_opts_out():
    client = MockNotionClient()
    svc = _make_svc(client)
    clf = _clf(task_id="t1", sync_to_notion=False)
    result = svc.sync("t1", None, clf, _ts())
    assert result.status == "skipped"
    assert len(client.created_pages) == 0


def test_sync_idempotent_second_call_returns_already_synced():
    client = MockNotionClient()
    svc = _make_svc(client)
    svc.sync("t1", "a1", _clf(task_id="t1"), _ts())
    result2 = svc.sync("t1", "a1", _clf(task_id="t1"), _ts())
    assert result2.status == "already_synced"
    assert len(client.created_pages) == 1


def test_sync_updates_existing_notion_page():
    existing_id = "existing-page-001"
    client = MockNotionClient(existing_page_id=existing_id)
    svc = _make_svc(client)
    result = svc.sync("t1", "a1", _clf(task_id="t1"), _ts())
    assert result.status == "updated"
    assert result.page_id == existing_id
    assert len(client.updated_pages) == 1
    assert len(client.created_pages) == 0


def test_sync_failed_auth_does_not_raise():
    client = MockNotionClient(should_fail=True, fail_with="auth")
    svc = _make_svc(client)
    result = svc.sync("t1", None, _clf(task_id="t1"), _ts())
    assert result.status == "failed"
    assert result.error_category == "auth"


def test_sync_failed_timeout():
    client = MockNotionClient(should_fail=True, fail_with="timeout")
    svc = _make_svc(client)
    result = svc.sync("t1", None, _clf(task_id="t1"), _ts())
    assert result.status == "failed"
    assert result.error_category == "timeout"


def test_sync_failed_rate_limit():
    client = MockNotionClient(should_fail=True, fail_with="rate_limit")
    svc = _make_svc(client)
    result = svc.sync("t1", None, _clf(task_id="t1"), _ts())
    assert result.status == "failed"
    assert result.error_category == "rate_limit"


def test_sync_failed_unknown_error():
    client = MockNotionClient(should_fail=True, fail_with="unknown")
    svc = _make_svc(client)
    result = svc.sync("t1", None, _clf(task_id="t1"), _ts())
    assert result.status == "failed"


def test_sync_retry_after_failure():
    client = MockNotionClient(should_fail=True, fail_with="timeout")
    svc = _make_svc(client)
    svc.sync("t1", None, _clf(task_id="t1"), _ts())
    client._should_fail = False
    result = svc.sync("t1", None, _clf(task_id="t1"), _ts())
    assert result.status == "synced"


def test_low_confidence_sets_needs_review_in_result():
    client = MockNotionClient()
    svc = _make_svc(client)
    clf = _clf(task_id="t1", confidence=0.5, notion_status="Needs Review")
    result = svc.sync("t1", None, clf, _ts())
    assert result.needs_review is True


def test_no_duplicate_pages_on_restart():
    client = MockNotionClient()
    svc = _make_svc(client)
    svc.sync("t1", "a1", _clf(task_id="t1"), _ts())
    result = svc.sync("t1", "a1", _clf(task_id="t1"), _ts())
    assert len(client.created_pages) == 1
    assert result.status == "already_synced"


def test_get_status_returns_counts():
    svc = _make_svc(MockNotionClient())
    status = svc.get_status()
    assert "pending" in status
    assert "failed" in status
    assert "last_synced_at" in status


def test_get_status_counts_after_sync():
    client = MockNotionClient()
    svc = _make_svc(client)
    svc.sync("t1", None, _clf(task_id="t1"), _ts())
    status = svc.get_status()
    assert status["pending"] == 0
    assert status["last_synced_at"] is not None


def test_sync_pending_processes_failed_records():
    client = MockNotionClient(should_fail=True, fail_with="timeout")
    svc = _make_svc(client)
    svc.sync("t1", None, _clf(task_id="t1"), _ts())
    assert svc.get_status()["failed"] == 1
    client._should_fail = False
    results = svc.sync_pending(limit=10)
    assert any(r.status == "synced" for r in results)


def test_sync_by_task_id_not_found():
    svc = _make_svc()
    result = svc.sync_by_task_id("nonexistent")
    assert result.status == "not_found"


def test_sync_by_task_id_already_synced():
    client = MockNotionClient()
    svc = _make_svc(client)
    svc.sync("t1", "a1", _clf(task_id="t1"), _ts())
    # Prevent the client from returning existing_page so sync_by_task_id
    # hits the synced record check in the repo
    result = svc.sync_by_task_id("t1")
    assert result.status == "already_synced"


def test_sync_voice_message_type():
    client = MockNotionClient()
    svc = _make_svc(client)
    result = svc.sync(
        "t1", None, _clf(task_id="t1"), _ts(), channel="telegram", message_type="voice"
    )
    assert result.status == "synced"
    # Check source was set to Telegram Voice in properties
    page_props = client.created_pages[0]["properties"]
    assert page_props["Source"]["select"]["name"] == "Telegram Voice"
