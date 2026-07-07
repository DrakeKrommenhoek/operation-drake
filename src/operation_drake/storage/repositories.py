from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from operation_drake.models.database import (
    AgentRunORM,
    ArtifactORM,
    InboundMessageORM,
    IntentDecisionORM,
    NotionSyncORM,
    PendingCaptureORM,
    SeenMessageORM,
    TaskORM,
    TelegramReplyMapORM,
)
from operation_drake.models.schemas import (
    VALID_TRANSITIONS,
    AgentRunCreate,
    ArtifactCreate,
    InboundMessageCreate,
    IntentDecisionCreate,
    NotionSyncCreate,
    PendingCaptureCreate,
    SeenMessageCreate,
    TaskCreate,
    TaskStatus,
    TelegramReplyMapCreate,
)


def _uid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class MessageRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, data: InboundMessageCreate) -> InboundMessageORM:
        d = data.model_dump()
        metadata = d.pop("metadata", {})
        obj = InboundMessageORM(id=_uid(), **d)
        obj.metadata_ = metadata
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def get(self, message_id: str) -> InboundMessageORM | None:
        return self.session.get(InboundMessageORM, message_id)

    def update_status(self, message_id: str, status: str) -> None:
        obj = self.session.get(InboundMessageORM, message_id)
        if obj:
            obj.processing_status = status
            self.session.commit()


class TaskRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, data: TaskCreate) -> TaskORM:
        obj = TaskORM(id=_uid(), **data.model_dump())
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def get(self, task_id: str) -> TaskORM | None:
        return self.session.get(TaskORM, task_id)

    def list_recent(self, limit: int = 20) -> list[TaskORM]:
        return self.session.query(TaskORM).order_by(TaskORM.created_at.desc()).limit(limit).all()

    def transition(self, task_id: str, new_status: TaskStatus) -> TaskORM:
        obj = self.session.get(TaskORM, task_id)
        if not obj:
            raise ValueError(f"Task {task_id} not found")
        current = TaskStatus(obj.status)
        allowed = VALID_TRANSITIONS.get(current, [])
        if new_status not in allowed:
            raise ValueError(f"Invalid transition {current} -> {new_status}")
        obj.status = new_status.value
        if new_status == TaskStatus.running:
            obj.started_at = _now()
        if new_status in (TaskStatus.completed, TaskStatus.failed, TaskStatus.cancelled):
            obj.completed_at = _now()
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def set_error(self, task_id: str, error: str) -> None:
        obj = self.session.get(TaskORM, task_id)
        if obj:
            obj.error_message = error
            obj.status = TaskStatus.failed.value
            obj.completed_at = _now()
            self.session.commit()

    def approve(self, task_id: str) -> TaskORM:
        obj = self.session.get(TaskORM, task_id)
        if not obj:
            raise ValueError(f"Task {task_id} not found")
        obj.approval_status = "approved"
        self.session.commit()
        return self.transition(task_id, TaskStatus.approved)

    def reject(self, task_id: str, reason: str = "") -> TaskORM:
        obj = self.session.get(TaskORM, task_id)
        if not obj:
            raise ValueError(f"Task {task_id} not found")
        obj.approval_status = "rejected"
        if reason:
            obj.error_message = f"Rejected: {reason}"
        self.session.commit()
        return self.transition(task_id, TaskStatus.cancelled)

    def list_awaiting_approval(self) -> list[TaskORM]:
        return (
            self.session.query(TaskORM)
            .filter(TaskORM.status == TaskStatus.awaiting_approval.value)
            .order_by(TaskORM.created_at.desc())
            .all()
        )

    def update_requested_action(self, task_id: str, new_action: str, new_type: str) -> None:
        obj = self.session.get(TaskORM, task_id)
        if obj:
            obj.requested_action = new_action
            obj.task_type = new_type
            self.session.commit()


class ArtifactRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, data: ArtifactCreate) -> ArtifactORM:
        obj = ArtifactORM(id=_uid(), **data.model_dump())
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def get_by_task(self, task_id: str) -> list[ArtifactORM]:
        return self.session.query(ArtifactORM).filter_by(task_id=task_id).all()


class IntentRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, data: IntentDecisionCreate) -> IntentDecisionORM:
        obj = IntentDecisionORM(id=_uid(), **data.model_dump())
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj


class AgentRunRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, data: AgentRunCreate) -> AgentRunORM:
        obj = AgentRunORM(id=_uid(), **data.model_dump())
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def complete(self, run_id: str, output_summary: str, token_count: int | None = None) -> None:
        obj = self.session.get(AgentRunORM, run_id)
        if obj:
            obj.completed_at = _now()
            obj.status = "completed"
            obj.output_summary = output_summary
            if token_count is not None:
                obj.token_count = token_count
            self.session.commit()

    def fail(self, run_id: str, error: str) -> None:
        obj = self.session.get(AgentRunORM, run_id)
        if obj:
            obj.completed_at = _now()
            obj.status = "failed"
            obj.error_info = error
            self.session.commit()

    def add_tokens(self, run_id: str, count: int) -> None:
        obj = self.session.get(AgentRunORM, run_id)
        if obj and count:
            obj.token_count = (obj.token_count or 0) + count
            self.session.commit()

    def get_total_tokens(self) -> int:
        from sqlalchemy import func

        result = self.session.query(func.sum(AgentRunORM.token_count)).scalar()
        return result or 0


class SeenMessageRepository:
    """Dedupe store: content hash -> the task that first captured it."""

    def __init__(self, session: Session):
        self.session = session

    def find_recent(self, hash_: str, within_days: int = 30) -> SeenMessageORM | None:
        cutoff = _now() - timedelta(days=within_days)
        return (
            self.session.query(SeenMessageORM)
            .filter(SeenMessageORM.hash == hash_, SeenMessageORM.created_at >= cutoff)
            .first()
        )

    def record(self, hash_: str, task_id: str) -> SeenMessageORM:
        existing = self.session.get(SeenMessageORM, hash_)
        if existing:
            existing.task_id = task_id
            existing.created_at = _now()
            self.session.commit()
            return existing
        obj = SeenMessageORM(**SeenMessageCreate(hash=hash_, task_id=task_id).model_dump())
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj


class TelegramReplyMapRepository:
    """Maps a bot-sent Telegram message id to the task it reported on."""

    def __init__(self, session: Session):
        self.session = session

    def record(self, telegram_message_id: str, task_id: str) -> TelegramReplyMapORM:
        obj = TelegramReplyMapORM(
            **TelegramReplyMapCreate(
                telegram_message_id=telegram_message_id, task_id=task_id
            ).model_dump()
        )
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def resolve(self, telegram_message_id: str) -> str | None:
        obj = self.session.get(TelegramReplyMapORM, telegram_message_id)
        return obj.task_id if obj else None


class PendingCaptureRepository:
    """Holds a single low-confidence capture per sender awaiting a y/n reply."""

    def __init__(self, session: Session):
        self.session = session

    def get(self, sender_id: str) -> PendingCaptureORM | None:
        return self.session.get(PendingCaptureORM, sender_id)

    def set(self, data: PendingCaptureCreate) -> PendingCaptureORM:
        existing = self.session.get(PendingCaptureORM, data.sender_id)
        if existing:
            self.session.delete(existing)
            self.session.flush()
        obj = PendingCaptureORM(**data.model_dump())
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def clear(self, sender_id: str) -> None:
        obj = self.session.get(PendingCaptureORM, sender_id)
        if obj:
            self.session.delete(obj)
            self.session.commit()


class NotionSyncRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, data: NotionSyncCreate) -> NotionSyncORM:
        obj = NotionSyncORM(id=_uid(), **data.model_dump())
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def get_by_idempotency_key(self, key: str) -> NotionSyncORM | None:
        return (
            self.session.query(NotionSyncORM).filter(NotionSyncORM.idempotency_key == key).first()
        )

    def get_by_task_id(self, task_id: str) -> NotionSyncORM | None:
        return self.session.query(NotionSyncORM).filter(NotionSyncORM.task_id == task_id).first()

    def record_attempt(self, sync_id: str) -> None:
        obj = self.session.get(NotionSyncORM, sync_id)
        if obj:
            obj.attempt_count += 1
            obj.last_attempt_at = _now()
            self.session.commit()

    def mark_synced(self, sync_id: str, page_id: str) -> None:
        obj = self.session.get(NotionSyncORM, sync_id)
        if obj:
            obj.sync_status = "synced"
            obj.external_page_id = page_id
            obj.last_error_category = None
            self.session.commit()

    def mark_failed(self, sync_id: str, error_category: str) -> None:
        obj = self.session.get(NotionSyncORM, sync_id)
        if obj:
            obj.sync_status = "failed"
            obj.last_error_category = error_category
            self.session.commit()

    def list_pending(self, limit: int = 50) -> list[NotionSyncORM]:
        return (
            self.session.query(NotionSyncORM)
            .filter(NotionSyncORM.sync_status.in_(["pending", "failed"]))
            .order_by(NotionSyncORM.created_at.asc())
            .limit(limit)
            .all()
        )

    def count_pending(self) -> int:
        return (
            self.session.query(NotionSyncORM).filter(NotionSyncORM.sync_status == "pending").count()
        )

    def count_failed(self) -> int:
        return (
            self.session.query(NotionSyncORM).filter(NotionSyncORM.sync_status == "failed").count()
        )

    def get_last_synced_at(self) -> datetime | None:
        obj = (
            self.session.query(NotionSyncORM)
            .filter(NotionSyncORM.sync_status == "synced")
            .order_by(NotionSyncORM.updated_at.desc())
            .first()
        )
        return obj.updated_at if obj else None
