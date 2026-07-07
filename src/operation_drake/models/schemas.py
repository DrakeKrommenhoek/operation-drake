from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def _uid() -> str:
    return str(uuid.uuid4())


class TaskStatus(StrEnum):
    received = "received"
    normalizing = "normalizing"
    interpreting = "interpreting"
    awaiting_approval = "awaiting_approval"
    approved = "approved"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


VALID_TRANSITIONS: dict[TaskStatus, list[TaskStatus]] = {
    TaskStatus.received: [TaskStatus.normalizing, TaskStatus.failed],
    TaskStatus.normalizing: [TaskStatus.interpreting, TaskStatus.failed],
    TaskStatus.interpreting: [TaskStatus.awaiting_approval, TaskStatus.approved, TaskStatus.failed],
    TaskStatus.awaiting_approval: [TaskStatus.approved, TaskStatus.cancelled, TaskStatus.failed],
    TaskStatus.approved: [TaskStatus.running, TaskStatus.failed],
    TaskStatus.running: [TaskStatus.completed, TaskStatus.failed],
    TaskStatus.completed: [],
    TaskStatus.failed: [],
    TaskStatus.cancelled: [],
}


class IntentType(StrEnum):
    save_note = "save_note"
    summarize = "summarize"
    extract_actions = "extract_actions"
    research_brief = "research_brief"
    save_link = "save_link"
    transcribe_voice = "transcribe_voice"
    clarify = "clarify"
    unknown = "unknown"


class MessageType(StrEnum):
    text = "text"
    voice = "voice"
    url = "url"
    document = "document"
    forwarded = "forwarded"
    command = "command"


class InboundMessageCreate(BaseModel):
    channel: str
    external_message_id: str = Field(default_factory=_uid)
    sender_id: str = ""
    raw_text: str = ""
    normalized_text: str = ""
    message_type: str = MessageType.text
    reply_to_message_id: str | None = None
    forwarded_from: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    processing_status: str = TaskStatus.received
    content_hash: str = ""


class InboundMessageRead(InboundMessageCreate):
    id: str
    received_at: datetime
    model_config = {"from_attributes": True}


class AttachmentCreate(BaseModel):
    inbound_message_id: str
    attachment_type: str
    filename: str = ""
    mime_type: str = ""
    source_url: str | None = None
    local_path: str | None = None
    transcript: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AttachmentRead(AttachmentCreate):
    id: str
    model_config = {"from_attributes": True}


class IntentDecisionCreate(BaseModel):
    inbound_message_id: str
    primary_intent: str
    secondary_intents: list[str] = Field(default_factory=list)
    confidence: float
    selected_workflow: str = ""
    proposed_action: str = ""
    approval_required: bool = True
    clarification_question: str | None = None
    rationale_summary: str = ""


class IntentDecisionRead(IntentDecisionCreate):
    id: str
    created_at: datetime
    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    inbound_message_id: str
    title: str
    task_type: str
    project: str | None = None
    status: str = TaskStatus.received
    priority: int = 5
    assigned_agent: str = ""
    approval_status: str = "pending"
    requested_action: str = ""


class TaskRead(TaskCreate):
    id: str
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    model_config = {"from_attributes": True}


class ArtifactCreate(BaseModel):
    task_id: str
    artifact_type: str
    title: str
    file_path: str
    content_preview: str = ""


class ArtifactRead(ArtifactCreate):
    id: str
    created_at: datetime
    model_config = {"from_attributes": True}


class AgentRunCreate(BaseModel):
    task_id: str
    agent_name: str
    model_provider: str = ""
    model_name: str = ""
    input_summary: str = ""
    output_summary: str = ""
    token_count: int | None = None
    error_info: str | None = None


class AgentRunRead(AgentRunCreate):
    id: str
    started_at: datetime
    completed_at: datetime | None = None
    status: str = "running"
    model_config = {"from_attributes": True}


class SeenMessageCreate(BaseModel):
    hash: str
    task_id: str


class TelegramReplyMapCreate(BaseModel):
    sender_id: str
    telegram_message_id: str
    task_id: str


class PendingCaptureCreate(BaseModel):
    sender_id: str
    channel: str
    raw_text: str = ""
    message_type: str = MessageType.text
    forwarded_from: str | None = None
    external_message_id: str | None = None
    inbound_message_id: str | None = None


class NotionSyncCreate(BaseModel):
    idempotency_key: str
    task_id: str
    artifact_id: str | None = None
    destination: str = "notion"
    sync_status: str = "pending"


class NotionSyncRead(NotionSyncCreate):
    id: str
    external_page_id: str | None = None
    attempt_count: int = 0
    last_attempt_at: datetime | None = None
    last_error_category: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
