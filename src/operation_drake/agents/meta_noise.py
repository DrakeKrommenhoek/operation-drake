from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from operation_drake.agents.base import BaseAgent
from operation_drake.llm.base import LLMProvider
from operation_drake.observability.logging import get_logger

logger = get_logger(__name__)

_PROMPT_PATH = Path("prompts/meta_noise_filter.md")

VALID_CATEGORIES = {"capture", "question", "command"}

# Deterministic pre-filter, run before any model call. Catches the obvious
# cases -- confirmation-seeking about a prior capture, and bot-directed
# instructions -- without spending a classifier call on them.
#
# The (?!['’]s) guards keep "Notion's roadmap" / "notion's" (possessive,
# genuine content) from satisfying "in notion" / "to notion". The (?!\s+by\b)
# guard on the "saved" pattern excludes passive-voice idioms like "saved by
# the bell", which otherwise collide with the literal substring "that saved".
_CONFIRMATION_PATTERNS = [
    re.compile(r"\bdid (that|this|it) (save|sync|go through|work)\b", re.IGNORECASE),
    re.compile(r"\bis (that|this|it) (in|on) notion\b(?!['’]s)", re.IGNORECASE),
    re.compile(r"\bwas (that|this|it) saved\b(?!\s+by\b)", re.IGNORECASE),
    re.compile(r"\bdid (that|this|it) (make|get) it (in|into|to) notion\b", re.IGNORECASE),
    re.compile(r"\bdid you (save|get|catch) (that|this|it)\b", re.IGNORECASE),
]

# The wildcard between the verb and "to"/"in notion" is bounded ([^.!?]{0,90})
# so it can span a list of objects ("add my X and my Y ... to notion") but
# can't cross a sentence boundary. \b directly before "to"/"in" (rather than
# relying on the literal words alone) stops "into notion" from satisfying "to
# notion" -- "into" has no word boundary before its trailing "to". The
# (?!['’]s) guard excludes the possessive "notion's" the same way as above.
_BOT_INSTRUCTION_PATTERNS = [
    re.compile(r"\badd (my|this|that|these) [^.!?]{0,90}?\bto notion\b(?!['’]s)", re.IGNORECASE),
    re.compile(r"\bput (this|that|these) in notion\b", re.IGNORECASE),
    re.compile(r"\bsync (this|that|these) to notion\b", re.IGNORECASE),
    re.compile(
        r"\bcan you (save|add|sync|put) [^.!?]{0,90}?\b(to|in) notion\b(?!['’]s)", re.IGNORECASE
    ),
]

# Bot-instruction patterns are only searched within this leading window --
# genuine commands are stated up front ("add X to notion"), so this stops a
# real instruction phrase from matching when it's tacked onto the end of an
# unrelated, substantive message (e.g. an idea, then "-- can you save that to
# Notion" as an afterthought). Confirmation patterns aren't windowed since
# those messages are typically short standalone questions.
_BOT_INSTRUCTION_WINDOW = 100


def keyword_prefilter(text: str) -> tuple[str, str] | None:
    """Deterministic keyword/regex triage for obvious meta-noise. Returns
    (category, matched_pattern) on a match; None if the message should
    fall through to the model-based MetaNoiseFilterAgent instead."""
    for pattern in _CONFIRMATION_PATTERNS:
        if pattern.search(text):
            return "confirmation_check", pattern.pattern
    window = text[:_BOT_INSTRUCTION_WINDOW]
    for pattern in _BOT_INSTRUCTION_PATTERNS:
        if pattern.search(window):
            return "bot_instruction", pattern.pattern
    return None


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
