from personal_agent_os.config import get_settings
from personal_agent_os.llm.base import LLMProvider


def get_llm_provider() -> LLMProvider:
    name = get_settings().default_llm_provider
    if name == "anthropic":
        from personal_agent_os.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    if name == "openai":
        from personal_agent_os.llm.openai_provider import OpenAIProvider
        return OpenAIProvider()
    from personal_agent_os.llm.mock_provider import MockLLMProvider
    return MockLLMProvider()
