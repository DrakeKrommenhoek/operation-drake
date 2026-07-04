import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from operation_drake.config import Settings
from operation_drake.models.database import Base
from operation_drake.models.schemas import NotionSyncCreate
from operation_drake.storage.repositories import NotionSyncRepository


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_notion_settings_default_disabled():
    s = Settings()
    assert s.notion_enabled is False
    assert s.notion_api_token == ""
    assert s.notion_low_confidence_threshold == 0.70


def test_notion_settings_sync_mode_default():
    s = Settings()
    assert s.notion_sync_mode == "automatic"


def test_notion_sync_orm_creates():
    session = _make_session()
    repo = NotionSyncRepository(session)
    record = repo.create(NotionSyncCreate(
        idempotency_key="notion:task-1",
        task_id="task-1",
    ))
    assert record.id
    assert record.sync_status == "pending"
    assert record.attempt_count == 0
    assert record.destination == "notion"


def test_notion_sync_idempotency_key_unique():
    session = _make_session()
    repo = NotionSyncRepository(session)
    repo.create(NotionSyncCreate(idempotency_key="notion:task-1", task_id="task-1"))
    with pytest.raises(Exception):
        repo.create(NotionSyncCreate(idempotency_key="notion:task-1", task_id="task-1"))


def test_notion_sync_mark_synced():
    session = _make_session()
    repo = NotionSyncRepository(session)
    record = repo.create(NotionSyncCreate(idempotency_key="notion:task-2", task_id="task-2"))
    repo.record_attempt(record.id)
    repo.mark_synced(record.id, "page-abc")
    updated = repo.get_by_idempotency_key("notion:task-2")
    assert updated.sync_status == "synced"
    assert updated.external_page_id == "page-abc"
    assert updated.attempt_count == 1


def test_notion_sync_mark_failed():
    session = _make_session()
    repo = NotionSyncRepository(session)
    record = repo.create(NotionSyncCreate(idempotency_key="notion:task-3", task_id="task-3"))
    repo.record_attempt(record.id)
    repo.mark_failed(record.id, "timeout")
    updated = repo.get_by_idempotency_key("notion:task-3")
    assert updated.sync_status == "failed"
    assert updated.last_error_category == "timeout"


def test_notion_sync_count_pending_and_failed():
    session = _make_session()
    repo = NotionSyncRepository(session)
    r1 = repo.create(NotionSyncCreate(idempotency_key="k1", task_id="t1"))
    r2 = repo.create(NotionSyncCreate(idempotency_key="k2", task_id="t2"))
    repo.mark_failed(r2.id, "auth")
    assert repo.count_pending() == 1
    assert repo.count_failed() == 1


def test_notion_sync_get_by_task_id():
    session = _make_session()
    repo = NotionSyncRepository(session)
    repo.create(NotionSyncCreate(idempotency_key="k-t99", task_id="t99"))
    found = repo.get_by_task_id("t99")
    assert found is not None
    assert found.task_id == "t99"


def test_notion_sync_list_pending_includes_failed():
    session = _make_session()
    repo = NotionSyncRepository(session)
    r1 = repo.create(NotionSyncCreate(idempotency_key="k1", task_id="t1"))
    r2 = repo.create(NotionSyncCreate(idempotency_key="k2", task_id="t2"))
    repo.mark_failed(r2.id, "timeout")
    pending = repo.list_pending()
    task_ids = {r.task_id for r in pending}
    assert "t1" in task_ids
    assert "t2" in task_ids


def test_notion_sync_get_last_synced_at_none_when_no_synced():
    session = _make_session()
    repo = NotionSyncRepository(session)
    assert repo.get_last_synced_at() is None


def test_notion_sync_get_last_synced_at_returns_timestamp():
    session = _make_session()
    repo = NotionSyncRepository(session)
    record = repo.create(NotionSyncCreate(idempotency_key="k1", task_id="t1"))
    repo.mark_synced(record.id, "page-xyz")
    ts = repo.get_last_synced_at()
    assert ts is not None
