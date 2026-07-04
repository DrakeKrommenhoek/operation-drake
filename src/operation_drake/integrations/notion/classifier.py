from __future__ import annotations

from pathlib import Path

from operation_drake.agents.base import BaseAgent
from operation_drake.integrations.notion.models import NotionClassification
from operation_drake.llm.base import LLMProvider
from operation_drake.observability.logging import get_logger

logger = get_logger(__name__)

_PROMPT_PATH = Path("prompts/notion_classifier.md")

_VALID_PROJECTS = {
    "General",
    "Business Ideas",
    "The Answer Movement",
    "Ascend",
    "Operation D.R.A.K.E.",
    "DK Personal Health OS",
    "Career & Work",
    "School & Learning",
    "Health & Fitness",
    "Investing & Finance",
    "Relationships & Networking",
    "Personal Life",
}

_VALID_CONTENT_TYPES = {
    "Idea",
    "Reflection",
    "Research",
    "Resource",
    "Action Plan",
    "Meeting Note",
    "Decision",
    "Journal Entry",
    "Workday Check-in",
    "Article or Media Capture",
    "Voice Memo",
    "General Note",
}

_VALID_CONTEXTS = {
    "General",
    "Pre-work Drive",
    "Post-work Drive",
    "Commute",
    "Work",
    "School",
    "Workout",
    "Evening Reflection",
    "Weekend Planning",
}


class NotionClassifier(BaseAgent):
    def __init__(self, llm: LLMProvider, low_confidence_threshold: float = 0.70):
        super().__init__(llm)
        self._threshold = low_confidence_threshold
        self._prompt_template = _PROMPT_PATH.read_text() if _PROMPT_PATH.exists() else ""

    def classify(
        self,
        content: str,
        workflow_summary: str = "",
        intent: str = "",
        channel: str = "telegram",
        message_type: str = "text",
        existing_project: str | None = None,
    ) -> NotionClassification:
        if self._prompt_template:
            prompt = (
                self._prompt_template.replace("{content}", content[:2000])
                .replace("{workflow_summary}", workflow_summary[:1000])
                .replace("{intent}", intent)
                .replace("{channel}", channel)
                .replace("{message_type}", message_type)
                .replace("{existing_project}", existing_project or "none")
            )
        else:
            prompt = f"Classify for Notion: {content[:300]}"

        try:
            resp = self.llm.complete(
                prompt=prompt,
                system="You are a classification agent. Respond with valid JSON only.",
            )
            data = self._parse_json(resp.content)
        except Exception as e:
            logger.warning({"action": "notion_classify_failed", "error": str(e)[:100]})
            return NotionClassification(
                title=content[:80],
                confidence=0.0,
                notion_status="Needs Review",
            )

        project = data.get("project", "General")
        if project not in _VALID_PROJECTS:
            project = "General"

        content_type = data.get("content_type", "General Note")
        if content_type not in _VALID_CONTENT_TYPES:
            content_type = "General Note"

        capture_context = data.get("capture_context", "General")
        if capture_context not in _VALID_CONTEXTS:
            capture_context = "General"

        confidence = float(data.get("confidence", 0.5))
        notion_status = "Inbox" if confidence >= self._threshold else "Needs Review"
        if data.get("notion_status") == "Needs Review":
            notion_status = "Needs Review"

        return NotionClassification(
            project=project,
            content_type=content_type,
            title=str(data.get("title", content[:80]))[:200],
            summary=str(data.get("summary", "")),
            tags=[str(t) for t in data.get("tags", []) if isinstance(t, str)][:10],
            actionable=bool(data.get("actionable", False)),
            next_action=str(data.get("next_action", "")),
            capture_context=capture_context,
            confidence=confidence,
            sync_to_notion=bool(data.get("sync_to_notion", True)),
            notion_status=notion_status,
        )
