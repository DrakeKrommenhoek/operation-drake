from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, prompt: str, system: str = "", **kwargs) -> LLMResponse: ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...
