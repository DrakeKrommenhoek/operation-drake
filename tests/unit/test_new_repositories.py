from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from operation_drake.models.database import Base, SeenMessageORM
from operation_drake.models.schemas import InboundMessageCreate, PendingCaptureCreate, TaskCreate
from operation_drake.storage.repositories import (
    MessageRepository,
    PendingCaptureRepository,
    SeenMessageRepository,
    TaskRepository,
    TelegramReplyMapRepository,
)


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


# ---------------------------------------------------------------------------
# SeenMessageRepository
# ---------------------------------------------------------------------------


def test_seen_message_record_and_find_recent():
    session = _make_session()
    repo = SeenMessageRepository(session)
    repo.record("hash-1", "task-1")
    found = repo.find_recent("hash-1")
    assert found is not None
    assert found.task_id == "task-1"


def test_seen_message_find_recent_returns_none_for_unknown_hash():
    session = _make_session()
    repo = SeenMessageRepository(session)
    assert repo.find_recent("no-such-hash") is None


def test_seen_message_expires_outside_window():
    session = _make_session()
    repo = SeenMessageRepository(session)
    repo.record("hash-1", "task-1")
    obj = session.get(SeenMessageORM, "hash-1")
    obj.created_at = datetime.now(UTC) - timedelta(days=31)
    session.commit()
    assert repo.find_recent("hash-1", within_days=30) is None


def test_seen_message_within_window_at_boundary():
    session = _make_session()
    repo = SeenMessageRepository(session)
    repo.record("hash-1", "task-1")
    obj = session.get(SeenMessageORM, "hash-1")
    obj.created_at = datetime.now(UTC) - timedelta(days=29)
    session.commit()
    assert repo.find_recent("hash-1", within_days=30) is not None


def test_seen_message_record_overwrites_existing_hash():
    session = _make_session()
    repo = SeenMessageRepository(session)
    repo.record("hash-1", "task-1")
    repo.record("hash-1", "task-2")
    assert repo.find_recent("hash-1").task_id == "task-2"


# ---------------------------------------------------------------------------
# TelegramReplyMapRepository
# ---------------------------------------------------------------------------


def test_telegram_reply_map_record_and_resolve():
    session = _make_session()
    repo = TelegramReplyMapRepository(session)
    repo.record("u1", "msg-100", "task-1")
    assert repo.resolve("u1", "msg-100") == "task-1"


def test_telegram_reply_map_resolve_unknown_returns_none():
    session = _make_session()
    repo = TelegramReplyMapRepository(session)
    assert repo.resolve("u1", "msg-999") is None


def test_telegram_reply_map_scoped_per_sender():
    session = _make_session()
    repo = TelegramReplyMapRepository(session)
    repo.record("u1", "msg-5", "task-a")
    repo.record("u2", "msg-5", "task-b")
    assert repo.resolve("u1", "msg-5") == "task-a"
    assert repo.resolve("u2", "msg-5") == "task-b"


# ---------------------------------------------------------------------------
# PendingCaptureRepository
# ---------------------------------------------------------------------------


def test_pending_capture_set_and_get():
    session = _make_session()
    repo = PendingCaptureRepository(session)
    repo.set(PendingCaptureCreate(sender_id="u1", channel="telegram", raw_text="maybe this"))
    pending = repo.get("u1")
    assert pending is not None
    assert pending.raw_text == "maybe this"


def test_pending_capture_get_returns_none_when_absent():
    session = _make_session()
    repo = PendingCaptureRepository(session)
    assert repo.get("u1") is None


def test_pending_capture_set_replaces_existing_for_same_sender():
    session = _make_session()
    repo = PendingCaptureRepository(session)
    repo.set(PendingCaptureCreate(sender_id="u1", channel="telegram", raw_text="first"))
    repo.set(PendingCaptureCreate(sender_id="u1", channel="telegram", raw_text="second"))
    pending = repo.get("u1")
    assert pending.raw_text == "second"


def test_pending_capture_clear_removes_it():
    session = _make_session()
    repo = PendingCaptureRepository(session)
    repo.set(PendingCaptureCreate(sender_id="u1", channel="telegram", raw_text="maybe this"))
    repo.clear("u1")
    assert repo.get("u1") is None


# ---------------------------------------------------------------------------
# TaskRepository.list_recent_by_sender
# ---------------------------------------------------------------------------


def _create_task_for_sender(session, sender_id: str, title: str):
    msg = MessageRepository(session).create(
        InboundMessageCreate(channel="telegram", sender_id=sender_id, raw_text=title)
    )
    return TaskRepository(session).create(
        TaskCreate(inbound_message_id=msg.id, title=title, task_type="save_note")
    )


def test_list_recent_by_sender_only_returns_that_senders_tasks():
    session = _make_session()
    _create_task_for_sender(session, "u1", "u1 first note")
    task_b = _create_task_for_sender(session, "u2", "u2 note")
    recent = TaskRepository(session).list_recent_by_sender("u2", limit=5)
    assert [t.id for t in recent] == [task_b.id]


def test_list_recent_by_sender_orders_most_recent_first():
    session = _make_session()
    older = _create_task_for_sender(session, "u1", "older")
    newer = _create_task_for_sender(session, "u1", "newer")
    older.created_at = datetime.now(UTC) - timedelta(minutes=5)
    session.commit()
    recent = TaskRepository(session).list_recent_by_sender("u1", limit=1)
    assert recent[0].id == newer.id
