from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class InboundMessageORM(Base):
    __tablename__ = "inbound_messages"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    channel: Mapped[str] = mapped_column(String, nullable=False)
    external_message_id: Mapped[str] = mapped_column(String, default=_uid)
    sender_id: Mapped[str] = mapped_column(String, default="")
    received_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    raw_text: Mapped[str] = mapped_column(Text, default="")
    normalized_text: Mapped[str] = mapped_column(Text, default="")
    message_type: Mapped[str] = mapped_column(String, default="text")
    reply_to_message_id: Mapped[str | None] = mapped_column(String, nullable=True)
    forwarded_from: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    processing_status: Mapped[str] = mapped_column(String, default="received")


class AttachmentORM(Base):
    __tablename__ = "attachments"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    inbound_message_id: Mapped[str] = mapped_column(String, nullable=False)
    attachment_type: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[str] = mapped_column(String, default="")
    mime_type: Mapped[str] = mapped_column(String, default="")
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    local_path: Mapped[str | None] = mapped_column(String, nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class IntentDecisionORM(Base):
    __tablename__ = "intent_decisions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    inbound_message_id: Mapped[str] = mapped_column(String, nullable=False)
    primary_intent: Mapped[str] = mapped_column(String, nullable=False)
    secondary_intents: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    selected_workflow: Mapped[str] = mapped_column(String, default="")
    proposed_action: Mapped[str] = mapped_column(Text, default="")
    approval_required: Mapped[bool] = mapped_column(Integer, default=True)
    clarification_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale_summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TaskORM(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    inbound_message_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    task_type: Mapped[str] = mapped_column(String, nullable=False)
    project: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="received")
    priority: Mapped[int] = mapped_column(Integer, default=5)
    assigned_agent: Mapped[str] = mapped_column(String, default="")
    approval_status: Mapped[str] = mapped_column(String, default="pending")
    requested_action: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ArtifactORM(Base):
    __tablename__ = "artifacts"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    task_id: Mapped[str] = mapped_column(String, nullable=False)
    artifact_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    content_preview: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AgentRunORM(Base):
    __tablename__ = "agent_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    task_id: Mapped[str] = mapped_column(String, nullable=False)
    agent_name: Mapped[str] = mapped_column(String, nullable=False)
    model_provider: Mapped[str] = mapped_column(String, default="")
    model_name: Mapped[str] = mapped_column(String, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, default="running")
    input_summary: Mapped[str] = mapped_column(Text, default="")
    output_summary: Mapped[str] = mapped_column(Text, default="")
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_info: Mapped[str | None] = mapped_column(Text, nullable=True)
