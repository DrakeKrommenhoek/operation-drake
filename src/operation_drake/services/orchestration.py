from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from operation_drake.agents.capture import CaptureAgent
from operation_drake.agents.router import RouterAgent
from operation_drake.agents.synthesis import SynthesisAgent
from operation_drake.ingestion.normalizer import normalize_message
from operation_drake.llm.base import LLMProvider
from operation_drake.models.schemas import (
    AgentRunCreate,
    ArtifactCreate,
    InboundMessageCreate,
    IntentDecisionCreate,
    TaskCreate,
    TaskStatus,
)
from operation_drake.observability.logging import get_logger
from operation_drake.services.artifact_service import ArtifactService
from operation_drake.services.project_classifier import classify_project
from operation_drake.storage.repositories import (
    AgentRunRepository,
    ArtifactRepository,
    IntentRepository,
    MessageRepository,
    TaskRepository,
)
from operation_drake.transcription.base import TranscriptionProvider
from operation_drake.workflows.capture_note import CaptureNoteWorkflow
from operation_drake.workflows.create_research_brief import CreateResearchBriefWorkflow
from operation_drake.workflows.extract_actions import ExtractActionsWorkflow
from operation_drake.workflows.process_voice_note import ProcessVoiceNoteWorkflow
from operation_drake.workflows.summarize import SummarizeWorkflow

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
    session_tokens: int = 0


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
            session_tokens = self._run_repo.get_total_tokens()
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
                session_tokens=session_tokens,
            )

        self._task_repo.transition(task.id, TaskStatus.normalizing)
        self._task_repo.transition(task.id, TaskStatus.interpreting)
        self._task_repo.transition(task.id, TaskStatus.approved)
        self._task_repo.transition(task.id, TaskStatus.running)

        artifact_path, result_summary, wf_tokens = self._execute_workflow(
            intent=decision.primary_intent,
            content=normalized.normalized_text,
            task_id=task.id,
            project=project,
            attachment_path=attachment_path,
        )
        if wf_tokens:
            self._run_repo.add_tokens(run.id, wf_tokens)

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

    def execute_approved_task(self, task_id: str) -> ProcessResult:
        """Approve and execute a task that is awaiting approval."""
        task = self._task_repo.get(task_id)
        if not task:
            return ProcessResult(
                message_id="",
                task_id=task_id,
                intent="",
                confidence=0.0,
                proposed_action="",
                status="not_found",
                approval_required=False,
                clarification_question=None,
                artifact_path=None,
                result_summary=f"Task {task_id} not found.",
            )
        if task.status != TaskStatus.awaiting_approval.value:
            return ProcessResult(
                message_id=task.inbound_message_id,
                task_id=task_id,
                intent=task.task_type,
                confidence=0.0,
                proposed_action=task.requested_action,
                status=task.status,
                approval_required=False,
                clarification_question=None,
                artifact_path=None,
                result_summary=f"Task is {task.status}, not awaiting_approval.",
            )

        msg = self._msg_repo.get(task.inbound_message_id)
        content = msg.normalized_text if msg else task.requested_action

        self._task_repo.approve(task_id)
        self._task_repo.transition(task_id, TaskStatus.running)

        run = self._run_repo.create(
            AgentRunCreate(
                task_id=task_id,
                agent_name=task.assigned_agent or "synthesis",
                model_provider=self._capture_agent.llm.provider_name,
                model_name=self._capture_agent.llm.model_name,
                input_summary=content[:200],
            )
        )

        try:
            artifact_path, result_summary, wf_tokens = self._execute_workflow(
                intent=task.task_type,
                content=content,
                task_id=task_id,
                project=task.project,
                attachment_path=None,
            )
            self._task_repo.transition(task_id, TaskStatus.completed)
            self._run_repo.complete(run.id, output_summary=result_summary, token_count=wf_tokens or None)
            if artifact_path:
                self._artifact_repo.create(
                    ArtifactCreate(
                        task_id=task_id,
                        artifact_type=task.task_type,
                        title=task.title,
                        file_path=artifact_path,
                        content_preview=result_summary[:200],
                    )
                )
            return ProcessResult(
                message_id=task.inbound_message_id,
                task_id=task_id,
                intent=task.task_type,
                confidence=1.0,
                proposed_action=task.requested_action,
                status=TaskStatus.completed.value,
                approval_required=False,
                clarification_question=None,
                artifact_path=artifact_path,
                result_summary=result_summary,
            )
        except Exception as e:
            self._task_repo.set_error(task_id, str(e))
            self._run_repo.fail(run.id, str(e))
            logger.error(
                {"action": "approved_workflow_failed", "task_id": task_id, "error": str(e)}
            )
            return ProcessResult(
                message_id=task.inbound_message_id,
                task_id=task_id,
                intent=task.task_type,
                confidence=1.0,
                proposed_action=task.requested_action,
                status=TaskStatus.failed.value,
                approval_required=False,
                clarification_question=None,
                artifact_path=None,
                result_summary=f"Workflow failed: {str(e)[:200]}",
            )

    def reject_task(self, task_id: str) -> ProcessResult:
        """Reject a task that is awaiting approval."""
        task = self._task_repo.get(task_id)
        if not task:
            return ProcessResult(
                message_id="",
                task_id=task_id,
                intent="",
                confidence=0.0,
                proposed_action="",
                status="not_found",
                approval_required=False,
                clarification_question=None,
                artifact_path=None,
                result_summary=f"Task {task_id} not found.",
            )
        if task.status != TaskStatus.awaiting_approval.value:
            return ProcessResult(
                message_id=task.inbound_message_id,
                task_id=task_id,
                intent=task.task_type,
                confidence=0.0,
                proposed_action=task.requested_action,
                status=task.status,
                approval_required=False,
                clarification_question=None,
                artifact_path=None,
                result_summary=f"Task is {task.status}, not awaiting_approval.",
            )
        self._task_repo.reject(task_id, reason="User rejected via /reject command")
        logger.info({"action": "task_rejected", "task_id": task_id})
        return ProcessResult(
            message_id=task.inbound_message_id,
            task_id=task_id,
            intent=task.task_type,
            confidence=0.0,
            proposed_action=task.requested_action,
            status=TaskStatus.cancelled.value,
            approval_required=False,
            clarification_question=None,
            artifact_path=None,
            result_summary="Task rejected and cancelled.",
        )

    def correct_task(self, task_id: str, correction: str) -> ProcessResult:
        """Re-interpret a pending task using user-provided correction text."""
        task = self._task_repo.get(task_id)
        if not task:
            return ProcessResult(
                message_id="",
                task_id=task_id,
                intent="",
                confidence=0.0,
                proposed_action="",
                status="not_found",
                approval_required=False,
                clarification_question=None,
                artifact_path=None,
                result_summary=f"Task {task_id} not found.",
            )
        if task.status != TaskStatus.awaiting_approval.value:
            return ProcessResult(
                message_id=task.inbound_message_id,
                task_id=task_id,
                intent=task.task_type,
                confidence=0.0,
                proposed_action=task.requested_action,
                status=task.status,
                approval_required=False,
                clarification_question=None,
                artifact_path=None,
                result_summary=f"Task is {task.status}. Only awaiting_approval tasks can be corrected.",
            )

        from operation_drake.ingestion.normalizer import normalize_message

        normalized = normalize_message(correction, "text")
        run = self._run_repo.create(
            AgentRunCreate(
                task_id=task_id,
                agent_name="router",
                model_provider=self._router.llm.provider_name,
                model_name=self._router.llm.model_name,
                input_summary=correction[:200],
            )
        )
        try:
            decision = self._router.route(
                normalized, channel="correction", message_id=task.inbound_message_id
            )
        except Exception as e:
            self._run_repo.fail(run.id, str(e))
            return ProcessResult(
                message_id=task.inbound_message_id,
                task_id=task_id,
                intent="unknown",
                confidence=0.0,
                proposed_action="",
                status=task.status,
                approval_required=True,
                clarification_question=None,
                artifact_path=None,
                result_summary=f"Re-interpretation failed: {str(e)[:100]}",
            )

        self._intent_repo.create(decision)
        self._task_repo.update_requested_action(
            task_id, decision.proposed_action, decision.primary_intent
        )
        self._run_repo.complete(run.id, output_summary=decision.rationale_summary)

        logger.info(
            {"action": "task_corrected", "task_id": task_id, "new_intent": decision.primary_intent}
        )
        return ProcessResult(
            message_id=task.inbound_message_id,
            task_id=task_id,
            intent=decision.primary_intent,
            confidence=decision.confidence,
            proposed_action=decision.proposed_action,
            status=task.status,
            approval_required=decision.approval_required,
            clarification_question=decision.clarification_question,
            artifact_path=None,
            result_summary=f"Re-interpreted as: {decision.proposed_action}",
        )

    def _execute_workflow(
        self,
        intent: str,
        content: str,
        task_id: str,
        project: str | None,
        attachment_path: str | None,
    ) -> tuple[str | None, str, int]:
        if intent == "save_note":
            r = CaptureNoteWorkflow(self._capture_agent, self._artifact_svc).run(
                content, task_id, project
            )
        elif intent == "summarize":
            r = SummarizeWorkflow(self._synthesis_agent, self._artifact_svc).run(content, task_id)
        elif intent == "extract_actions":
            r = ExtractActionsWorkflow(self._synthesis_agent, self._artifact_svc).run(
                content, task_id
            )
        elif intent == "research_brief":
            r = CreateResearchBriefWorkflow(self._synthesis_agent, self._artifact_svc).run(
                content, task_id
            )
        elif intent == "transcribe_voice" and attachment_path:
            r = ProcessVoiceNoteWorkflow(
                self._transcriber, self._synthesis_agent, self._artifact_svc
            ).run(attachment_path, task_id)
        elif intent == "save_link":
            r = CaptureNoteWorkflow(self._capture_agent, self._artifact_svc).run(
                f"Saved link: {content}", task_id, project
            )
        else:
            return None, "No workflow available for this intent.", 0
        return (
            (r.artifact_path if r.success else None),
            (r.summary if r.success else r.error),
            r.token_count if r.success else 0,
        )
