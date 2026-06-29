from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from personal_agent_os.agents.capture import CaptureAgent
from personal_agent_os.agents.router import RouterAgent
from personal_agent_os.agents.synthesis import SynthesisAgent
from personal_agent_os.ingestion.normalizer import normalize_message
from personal_agent_os.llm.base import LLMProvider
from personal_agent_os.models.schemas import (
    AgentRunCreate,
    ArtifactCreate,
    InboundMessageCreate,
    IntentDecisionCreate,
    TaskCreate,
    TaskStatus,
)
from personal_agent_os.observability.logging import get_logger
from personal_agent_os.services.artifact_service import ArtifactService
from personal_agent_os.services.project_classifier import classify_project
from personal_agent_os.storage.repositories import (
    AgentRunRepository,
    ArtifactRepository,
    IntentRepository,
    MessageRepository,
    TaskRepository,
)
from personal_agent_os.transcription.base import TranscriptionProvider
from personal_agent_os.workflows.capture_note import CaptureNoteWorkflow
from personal_agent_os.workflows.create_research_brief import CreateResearchBriefWorkflow
from personal_agent_os.workflows.extract_actions import ExtractActionsWorkflow
from personal_agent_os.workflows.process_voice_note import ProcessVoiceNoteWorkflow
from personal_agent_os.workflows.summarize import SummarizeWorkflow

logger = get_logger(__name__)

_AGENT_MAP = {
    "save_note": "capture",
    "save_link": "capture",
    "summarize": "synthesis",
    "extract_actions": "synthesis",
    "research_brief": "synthesis",
    "transcribe_voice": "synthesis",
}


@dataclass
class ProcessResult:
    message_id: str
    task_id: str
    intent: str
    confidence: float
    proposed_action: str
    status: str
    approval_required: bool
    clarification_question: str | None
    artifact_path: str | None
    result_summary: str


class OrchestratorService:
    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        transcriber: TranscriptionProvider,
        artifacts_dir: str,
    ):
        self._session = session
        self._msg_repo = MessageRepository(session)
        self._task_repo = TaskRepository(session)
        self._artifact_repo = ArtifactRepository(session)
        self._intent_repo = IntentRepository(session)
        self._run_repo = AgentRunRepository(session)
        self._router = RouterAgent(llm=llm)
        self._capture_agent = CaptureAgent(llm=llm)
        self._synthesis_agent = SynthesisAgent(llm=llm)
        self._transcriber = transcriber
        self._artifact_svc = ArtifactService(artifacts_dir=artifacts_dir)

    def process(
        self,
        channel: str,
        raw_text: str = "",
        message_type: str = "text",
        sender_id: str = "",
        forwarded_from: str | None = None,
        attachment_path: str | None = None,
        external_message_id: str | None = None,
    ) -> ProcessResult:
        normalized = normalize_message(raw_text, message_type, forwarded_from)

        msg = self._msg_repo.create(
            InboundMessageCreate(
                channel=channel,
                external_message_id=external_message_id or str(uuid.uuid4()),
                sender_id=sender_id,
                raw_text=raw_text,
                normalized_text=normalized.normalized_text,
                message_type=normalized.message_type,
                forwarded_from=forwarded_from,
                processing_status=TaskStatus.normalizing.value,
            )
        )
        self._msg_repo.update_status(msg.id, TaskStatus.interpreting.value)

        run = self._run_repo.create(
            AgentRunCreate(
                task_id="pending",
                agent_name="router",
                model_provider=self._router.llm.provider_name,
                model_name=self._router.llm.model_name,
                input_summary=normalized.normalized_text[:200],
            )
        )

        try:
            decision = self._router.route(normalized, channel=channel, message_id=msg.id)
        except Exception as e:
            logger.error({"action": "route_failed", "error": str(e)})
            decision = IntentDecisionCreate(
                inbound_message_id=msg.id,
                primary_intent="unknown",
                confidence=0.0,
                proposed_action="Could not classify intent",
                approval_required=True,
                rationale_summary=f"Routing failed: {str(e)[:100]}",
            )

        self._intent_repo.create(decision)
        project = classify_project(normalized.normalized_text)

        task = self._task_repo.create(
            TaskCreate(
                inbound_message_id=msg.id,
                title=(decision.proposed_action or normalized.normalized_text)[:100],
                task_type=decision.primary_intent,
                project=project,
                status=TaskStatus.received.value,
                assigned_agent=_AGENT_MAP.get(decision.primary_intent, "router"),
                approval_status="pending" if decision.approval_required else "auto_approved",
                requested_action=decision.proposed_action,
            )
        )

        run.task_id = task.id
        self._session.commit()
        self._run_repo.complete(run.id, output_summary=decision.rationale_summary)

        if decision.approval_required:
            self._task_repo.transition(task.id, TaskStatus.normalizing)
            self._task_repo.transition(task.id, TaskStatus.interpreting)
            self._task_repo.transition(task.id, TaskStatus.awaiting_approval)
            return ProcessResult(
                message_id=msg.id,
                task_id=task.id,
                intent=decision.primary_intent,
                confidence=decision.confidence,
                proposed_action=decision.proposed_action,
                status=TaskStatus.awaiting_approval.value,
                approval_required=True,
                clarification_question=decision.clarification_question,
                artifact_path=None,
                result_summary="Awaiting your approval.",
            )

        self._task_repo.transition(task.id, TaskStatus.normalizing)
        self._task_repo.transition(task.id, TaskStatus.interpreting)
        self._task_repo.transition(task.id, TaskStatus.approved)
        self._task_repo.transition(task.id, TaskStatus.running)

        artifact_path, result_summary = self._execute_workflow(
            intent=decision.primary_intent,
            content=normalized.normalized_text,
            task_id=task.id,
            project=project,
            attachment_path=attachment_path,
        )

        self._task_repo.transition(task.id, TaskStatus.completed)
        if artifact_path:
            self._artifact_repo.create(
                ArtifactCreate(
                    task_id=task.id,
                    artifact_type=decision.primary_intent,
                    title=task.title,
                    file_path=artifact_path,
                    content_preview=result_summary[:200],
                )
            )

        return ProcessResult(
            message_id=msg.id,
            task_id=task.id,
            intent=decision.primary_intent,
            confidence=decision.confidence,
            proposed_action=decision.proposed_action,
            status=TaskStatus.completed.value,
            approval_required=False,
            clarification_question=None,
            artifact_path=artifact_path,
            result_summary=result_summary,
        )

    def _execute_workflow(
        self,
        intent: str,
        content: str,
        task_id: str,
        project: str | None,
        attachment_path: str | None,
    ) -> tuple[str | None, str]:
        if intent == "save_note":
            r = CaptureNoteWorkflow(self._capture_agent, self._artifact_svc).run(content, task_id, project)
        elif intent == "summarize":
            r = SummarizeWorkflow(self._synthesis_agent, self._artifact_svc).run(content, task_id)
        elif intent == "extract_actions":
            r = ExtractActionsWorkflow(self._synthesis_agent, self._artifact_svc).run(content, task_id)
        elif intent == "research_brief":
            r = CreateResearchBriefWorkflow(self._synthesis_agent, self._artifact_svc).run(content, task_id)
        elif intent == "transcribe_voice" and attachment_path:
            r = ProcessVoiceNoteWorkflow(self._transcriber, self._synthesis_agent, self._artifact_svc).run(
                attachment_path, task_id
            )
        elif intent == "save_link":
            r = CaptureNoteWorkflow(self._capture_agent, self._artifact_svc).run(
                f"Saved link: {content}", task_id, project
            )
        else:
            return None, "No workflow available for this intent."
        return (r.artifact_path if r.success else None), (r.summary if r.success else r.error)
