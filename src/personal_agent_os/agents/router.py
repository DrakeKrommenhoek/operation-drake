from pathlib import Path

from personal_agent_os.agents.base import BaseAgent
from personal_agent_os.ingestion.normalizer import NormalizedMessage
from personal_agent_os.llm.base import LLMProvider
from personal_agent_os.models.schemas import IntentDecisionCreate
from personal_agent_os.observability.logging import get_logger

logger = get_logger(__name__)

_PROMPT_PATH = Path("prompts/router.md")

SAFE_INTENTS = {"save_note", "summarize", "extract_actions", "research_brief", "save_link", "transcribe_voice"}

WORKFLOW_MAP = {
    "save_note": "capture_note",
    "summarize": "summarize",
    "extract_actions": "extract_actions",
    "research_brief": "create_research_brief",
    "save_link": "capture_note",
    "transcribe_voice": "process_voice_note",
    "clarify": "",
    "unknown": "",
}


class RouterAgent(BaseAgent):
    def __init__(self, llm: LLMProvider):
        super().__init__(llm)
        self._prompt_template = _PROMPT_PATH.read_text() if _PROMPT_PATH.exists() else ""

    def route(self, normalized: NormalizedMessage, channel: str, message_id: str) -> IntentDecisionCreate:
        if self._prompt_template:
            prompt = self._prompt_template.format(
                channel=channel,
                message_type=normalized.message_type,
                has_attachments="false",
                has_urls=str(bool(normalized.detected_urls)).lower(),
                normalized_text=normalized.normalized_text[:2000],
            )
        else:
            prompt = f"Classify intent for: {normalized.normalized_text[:500]}"

        resp = self.llm.complete(prompt=prompt, system="You are a routing agent. Respond with valid JSON only.")
        data = self._parse_json(resp.content)

        primary = data.get("primary_intent", "unknown")
        confidence = float(data.get("confidence", 0.5))
        approval_required = data.get("approval_required", primary not in SAFE_INTENTS)

        logger.info({"action": "route_decision", "intent": primary, "confidence": confidence, "message_id": message_id})

        return IntentDecisionCreate(
            inbound_message_id=message_id,
            primary_intent=primary,
            secondary_intents=data.get("secondary_intents", []),
            confidence=confidence,
            selected_workflow=WORKFLOW_MAP.get(primary, ""),
            proposed_action=data.get("proposed_action", ""),
            approval_required=approval_required,
            clarification_question=data.get("clarification_question"),
            rationale_summary=data.get("rationale_summary", ""),
        )
