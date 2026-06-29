from operation_drake.config import get_settings
from operation_drake.llm.base import LLMProvider

_VALID = ("anthropic", "openai", "mock")


def get_llm_provider() -> LLMProvider:
    name = get_settings().default_llm_provider
    if name == "anthropic":
        from operation_drake.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    if name == "openai":
        from operation_drake.llm.openai_provider import OpenAIProvider

        return OpenAIProvider()
    if name == "mock":
        from operation_drake.llm.mock_provider import MockLLMProvider

        return MockLLMProvider()
    raise ValueError(f"Unknown DEFAULT_LLM_PROVIDER '{name}'. Valid values: {', '.join(_VALID)}")
