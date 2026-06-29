from dataclasses import dataclass, field
from pathlib import Path

from operation_drake.agents.base import BaseAgent
from operation_drake.llm.base import LLMProvider

_PROMPT_PATH = Path("prompts/synthesis.md")


@dataclass
class SynthesisResult:
    title: str
    summary: str
    key_points: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


class SynthesisAgent(BaseAgent):
    def __init__(self, llm: LLMProvider):
        super().__init__(llm)
        self._prompt_template = _PROMPT_PATH.read_text() if _PROMPT_PATH.exists() else ""

    def run_synthesis(self, content: str, task_type: str) -> SynthesisResult:
        if self._prompt_template:
            prompt = self._prompt_template.format(task_type=task_type, content=content[:4000])
        else:
            prompt = f"Summarize ({task_type}): {content[:500]}"
        resp = self.llm.complete(
            prompt=prompt, system="You are a synthesis agent. Respond with valid JSON only."
        )
        data = self._parse_json(resp.content)
        return SynthesisResult(
            title=data.get("title", "Synthesis Result"),
            summary=data.get("summary", ""),
            key_points=data.get("key_points", []),
            action_items=data.get("action_items", []),
            questions=data.get("questions", []),
            next_steps=data.get("next_steps", []),
        )
