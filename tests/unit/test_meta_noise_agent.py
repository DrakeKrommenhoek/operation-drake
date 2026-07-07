from __future__ import annotations

from operation_drake.agents.meta_noise import MetaNoiseFilterAgent
from operation_drake.llm.mock_provider import MockLLMProvider


def test_classify_defaults_to_capture_high_confidence():
    agent = MetaNoiseFilterAgent(llm=MockLLMProvider())
    result = agent.classify("A business idea about protein shakes")
    assert result.category == "capture"
    assert result.confidence == 90


def test_classify_parses_question_category():
    llm = MockLLMProvider(
        fixed_response='{"category":"question","confidence":88,"answer":"42","rationale":"asking"}'
    )
    result = MetaNoiseFilterAgent(llm=llm).classify("what's the answer?")
    assert result.category == "question"
    assert result.confidence == 88
    assert result.answer == "42"


def test_classify_rejects_invalid_category_falls_back_to_capture():
    llm = MockLLMProvider(fixed_response='{"category":"nonsense","confidence":50}')
    result = MetaNoiseFilterAgent(llm=llm).classify("something")
    assert result.category == "capture"


def test_classify_clamps_confidence_to_0_100():
    llm = MockLLMProvider(fixed_response='{"category":"capture","confidence":500}')
    result = MetaNoiseFilterAgent(llm=llm).classify("something")
    assert result.confidence == 100

    llm2 = MockLLMProvider(fixed_response='{"category":"capture","confidence":-10}')
    result2 = MetaNoiseFilterAgent(llm=llm2).classify("something")
    assert result2.confidence == 0


def test_classify_handles_malformed_json_gracefully():
    llm = MockLLMProvider(fixed_response="not json at all")
    result = MetaNoiseFilterAgent(llm=llm).classify("something")
    assert result.category == "capture"
    assert result.confidence == 100
