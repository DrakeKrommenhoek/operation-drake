import json
import re
from abc import ABC
from dataclasses import dataclass, field

from personal_agent_os.llm.base import LLMProvider


@dataclass
class AgentResult:
    success: bool
    output: dict = field(default_factory=dict)
    error: str = ""
    token_count: int = 0
    model_provider: str = ""
    model_name: str = ""


class BaseAgent(ABC):
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    @property
    def name(self) -> str:
        return self.__class__.__name__

    def _parse_json(self, text: str) -> dict:
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}
