from openai import OpenAI

from operation_drake.config import get_settings
from operation_drake.llm.base import LLMProvider, LLMResponse


class OpenAIProvider(LLMProvider):
    provider_name = "openai"
    model_name = "gpt-4o-mini"

    def __init__(self):
        self._client = OpenAI(api_key=get_settings().openai_api_key)

    def complete(self, prompt: str, system: str = "", **kwargs) -> LLMResponse:
        resp = self._client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": system
                    or "You are a helpful assistant. Respond with valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=1024,
        )
        content = resp.choices[0].message.content or ""
        usage = resp.usage
        return LLMResponse(
            content=content,
            provider="openai",
            model=self.model_name,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )
