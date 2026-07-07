from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from operation_drake.agents.base import BaseAgent
from operation_drake.llm.base import LLMProvider
from operation_drake.observability.logging import get_logger

logger = get_logger(__name__)

_PROMPT_PATH = Path("prompts/meta_noise_filter.md")

VALID_CATEGORIES = {"capture", "question", "command"}


@dataclass
class MetaNoiseResult:
    category: str = "capture"
    confidence: int = 100
    answer: str = ""
    rationale: str = ""


class MetaNoiseFilterAgent(BaseAgent):
    """Triages an inbound message as capture / question / command before
    it reaches the router, so casual chat never turns into a vault entry."""

    def __init__(self, llm: LLMProvider):
        super().__init__(llm)
        self._prompt_template = _PROMPT_PATH.read_text() if _PROMPT_PATH.exists() else ""

    def classify(self, text: str) -> MetaNoiseResult:
        if self._prompt_template:
            prompt = self._prompt_template.replace("{content}", text[:2000])
        else:
            prompt = f"Triage this message as capture, question, or command: {text[:500]}"

        try:
            resp = self.llm.complete(
                prompt=prompt,
                system="You are a message triage agent. Respond with valid JSON only.",
            )
            data = self._parse_json(resp.content)
        except Exception as e:
            logger.warning({"action": "meta_noise_classify_failed", "error": str(e)[:100]})
            return MetaNoiseResult(rationale="classification failed, defaulting to capture")

        category = data.get("category", "capture")
        if category not in VALID_CATEGORIES:
            category = "capture"

        try:
            confidence = int(data.get("confidence", 100))
        except (TypeError, ValueError):
            confidence = 100
        confidence = max(0, min(100, confidence))

        return MetaNoiseResult(
            category=category,
            confidence=confidence,
            answer=str(data.get("answer", "")),
            rationale=str(data.get("rationale", "")),
        )
