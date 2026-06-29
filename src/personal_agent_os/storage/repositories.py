from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from personal_agent_os.models.database import (
    AgentRunORM,
    ArtifactORM,
    InboundMessageORM,
    IntentDecisionORM,
    TaskORM,
)
from personal_agent_os.models.schemas import (
    VALID_TRANSITIONS,
    AgentRunCreate,
    ArtifactCreate,
    InboundMessageCreate,
    IntentDecisionCreate,
    TaskCreate,
    TaskStatus,
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
