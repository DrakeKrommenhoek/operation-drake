from dataclasses import dataclass, field
from pathlib import Path

from operation_drake.agents.base import BaseAgent
from operation_drake.llm.base import LLMProvider
from operation_drake.observability.logging import get_logger

logger = get_logger(__name__)

_PROMPT_PATH = Path("prompts/capture.md")


@dataclass
class CaptureResult:
    title: str
    project: str | None
    tags: list[str] = field(default_factory=list)
    summary: str = ""
    action_items: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0


class CaptureAgent(BaseAgent):
    def __init__(self, llm: LLMProvider):
        super().__init__(llm)
        self._prompt_template = _PROMPT_PATH.read_text() if _PROMPT_PATH.exists() else ""

    def run_capture(self, content: str, project: str | None = None) -> CaptureResult:
        from operation_drake.services.project_classifier import get_registry

        projects = ", ".join(f"{p['id']} ({p['name']})" for p in get_registry())
        if self._prompt_template:
            prompt = self._prompt_template.format(projects=projects, content=content[:3000])
        else:
            prompt = f"Extract metadata from: {content[:500]}"
        resp = self.llm.complete(
            prompt=prompt, system="You are a capture agent. Respond with valid JSON only."
        )
        data = self._parse_json(resp.content)
        return CaptureResult(
            title=data.get("title", content[:60]),
            project=data.get("project") or project,
            tags=data.get("tags", []),
            summary=data.get("summary", ""),
            action_items=data.get("action_items", []),
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
        )
