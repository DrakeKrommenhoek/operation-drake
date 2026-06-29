import anthropic

from operation_drake.config import get_settings
from operation_drake.llm.base import LLMProvider, LLMResponse


class AnthropicProvider(LLMProvider):
    provider_name = "anthropic"
    model_name = "claude-haiku-4-5-20251001"

    def __init__(self):
        self._client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)

    def complete(self, prompt: str, system: str = "", **kwargs) -> LLMResponse:
        msg = self._client.messages.create(
            model=self.model_name,
            max_tokens=1024,
            system=system or "You are a helpful assistant. Respond with valid JSON only.",
            messages=[{"role": "user", "content": prompt}],
        )
        content = msg.content[0].text if msg.content else ""
        return LLMResponse(
            content=content,
            provider="anthropic",
            model=self.model_name,
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
        )
