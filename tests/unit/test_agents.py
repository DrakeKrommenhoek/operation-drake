from operation_drake.agents.capture import CaptureAgent
from operation_drake.agents.router import RouterAgent
from operation_drake.agents.synthesis import SynthesisAgent
from operation_drake.ingestion.normalizer import normalize_message
from operation_drake.llm.mock_provider import MockLLMProvider


def test_router_returns_intent_decision():
    agent = RouterAgent(llm=MockLLMProvider())
    normalized = normalize_message("This is a note about my workout", "text")
    decision = agent.route(normalized, channel="cli", message_id="test-1")
    assert decision.primary_intent
    assert 0.0 <= decision.confidence <= 1.0
    assert isinstance(decision.approval_required, bool)
    assert decision.inbound_message_id == "test-1"


def test_router_handles_invalid_llm_response():
    bad_llm = MockLLMProvider(fixed_response="not json at all {{broken")
    agent = RouterAgent(llm=bad_llm)
    normalized = normalize_message("test message", "text")
    decision = agent.route(normalized, channel="cli", message_id="test-2")
    assert decision.primary_intent == "unknown"
    assert decision.confidence == 0.5


def test_capture_agent_runs():
    agent = CaptureAgent(llm=MockLLMProvider())
    result = agent.run_capture("Save this idea: build a morning routine tracker", project=None)
    assert result.title
    assert isinstance(result.tags, list)


def test_synthesis_agent_summarizes():
    agent = SynthesisAgent(llm=MockLLMProvider())
    result = agent.run_synthesis(
        "Long article text about Python performance goes here.", task_type="summarize"
    )
    assert result.title
    assert isinstance(result.key_points, list)
    assert isinstance(result.action_items, list)
