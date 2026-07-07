from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from operation_drake.integrations.notion.mock_client import MockNotionClient
from operation_drake.integrations.notion.models import match_project
from operation_drake.integrations.notion.sync_service import NotionSyncService
from operation_drake.models.database import Base
from operation_drake.services.writeback_service import WriteBackService
from operation_drake.storage.repositories import NotionSyncRepository


def _synced_task(session, task_id="task-1", page_id="page-1"):
    repo = NotionSyncRepository(session)
    from operation_drake.models.schemas import NotionSyncCreate

    record = repo.create(NotionSyncCreate(idempotency_key=f"notion:{task_id}", task_id=task_id))
    repo.mark_synced(record.id, page_id)
    return record


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


# ---------------------------------------------------------------------------
# match_project
# ---------------------------------------------------------------------------


def test_match_project_exact_case_insensitive():
    assert match_project("ascend") == "Ascend"


def test_match_project_substring():
    assert match_project("answer") == "The Answer Movement"


def test_match_project_fuzzy_typo():
    assert match_project("buisness ideas") == "Business Ideas"


def test_match_project_no_match_returns_none():
    assert match_project("something totally unrelated xyz") is None


def test_match_project_empty_returns_none():
    assert match_project("   ") is None


# ---------------------------------------------------------------------------
# NotionSyncService.update_properties
# ---------------------------------------------------------------------------


def test_update_properties_not_found_when_never_synced():
    session = _make_session()
    client = MockNotionClient()
    svc = NotionSyncService(session=session, client=client, database_id="db")
    result = svc.update_properties("no-such-task", {"Status": {"select": {"name": "Archived"}}})
    assert result.status == "not_found"


def test_update_properties_updates_synced_page():
    session = _make_session()
    client = MockNotionClient()
    _synced_task(session, task_id="task-1", page_id="page-1")
    svc = NotionSyncService(session=session, client=client, database_id="db")
    result = svc.update_properties("task-1", {"Status": {"select": {"name": "Archived"}}})
    assert result.status == "updated"
    assert client.updated_pages[-1]["id"] == "page-1"


def test_update_properties_reports_failure():
    session = _make_session()
    client = MockNotionClient(should_fail=True, fail_with="auth")
    _synced_task(session, task_id="task-1", page_id="page-1")
    svc = NotionSyncService(session=session, client=client, database_id="db")
    result = svc.update_properties("task-1", {"Status": {"select": {"name": "Archived"}}})
    assert result.status == "failed"
    assert result.error_category == "auth"


# ---------------------------------------------------------------------------
# WriteBackService
# ---------------------------------------------------------------------------


def test_writeback_not_enabled_when_no_notion_service():
    result = WriteBackService(None).mark_done("task-1")
    assert result.ok is False
    assert "not enabled" in result.message.lower()


def test_writeback_mark_done_sets_organized():
    session = _make_session()
    client = MockNotionClient()
    _synced_task(session)
    svc = NotionSyncService(session=session, client=client, database_id="db")
    result = WriteBackService(svc).mark_done("task-1")
    assert result.ok is True
    assert client.updated_pages[-1]["properties"]["Status"]["select"]["name"] == "Organized"


def test_writeback_mark_archived_sets_archived():
    session = _make_session()
    client = MockNotionClient()
    _synced_task(session)
    svc = NotionSyncService(session=session, client=client, database_id="db")
    result = WriteBackService(svc).mark_archived("task-1")
    assert result.ok is True
    assert client.updated_pages[-1]["properties"]["Status"]["select"]["name"] == "Archived"


def test_writeback_mark_action_required_sets_status_and_actionable():
    session = _make_session()
    client = MockNotionClient()
    _synced_task(session)
    svc = NotionSyncService(session=session, client=client, database_id="db")
    result = WriteBackService(svc).mark_action_required("task-1")
    assert result.ok is True
    props = client.updated_pages[-1]["properties"]
    assert props["Status"]["select"]["name"] == "Action Required"
    assert props["Actionable"]["checkbox"] is True


def test_writeback_set_project_matches_and_applies():
    session = _make_session()
    client = MockNotionClient()
    _synced_task(session)
    svc = NotionSyncService(session=session, client=client, database_id="db")
    result = WriteBackService(svc).set_project("task-1", "ascend")
    assert result.ok is True
    assert client.updated_pages[-1]["properties"]["Project"]["select"]["name"] == "Ascend"


def test_writeback_set_project_unmatched_lists_options():
    session = _make_session()
    client = MockNotionClient()
    _synced_task(session)
    svc = NotionSyncService(session=session, client=client, database_id="db")
    result = WriteBackService(svc).set_project("task-1", "gibberish xyz")
    assert result.ok is False
    assert "Options:" in result.message


def test_writeback_not_found_when_task_never_synced():
    session = _make_session()
    client = MockNotionClient()
    svc = NotionSyncService(session=session, client=client, database_id="db")
    result = WriteBackService(svc).mark_done("unknown-task")
    assert result.ok is False
