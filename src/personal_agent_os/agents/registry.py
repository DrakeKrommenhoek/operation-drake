from personal_agent_os.agents.base import BaseAgent
from personal_agent_os.llm import get_llm_provider

_registry: dict[str, BaseAgent] = {}


def get_agent(name: str) -> BaseAgent:
    if name not in _registry:
        llm = get_llm_provider()
        if name == "router":
            from personal_agent_os.agents.router import RouterAgent
            _registry[name] = RouterAgent(llm=llm)
        elif name == "capture":
            from personal_agent_os.agents.capture import CaptureAgent
            _registry[name] = CaptureAgent(llm=llm)
        elif name == "synthesis":
            from personal_agent_os.agents.synthesis import SynthesisAgent
            _registry[name] = SynthesisAgent(llm=llm)
        else:
            raise ValueError(f"Unknown agent: {name}")
    return _registry[name]


def list_agents() -> list[str]:
    return ["router", "capture", "synthesis"]
