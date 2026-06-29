from personal_agent_os.llm.mock_provider import MockLLMProvider
from personal_agent_os.transcription.mock_transcriber import MockTranscriber


def test_mock_llm_returns_content():
    provider = MockLLMProvider()
    resp = provider.complete(prompt="classify this intent", system="respond with json")
    assert resp.content
    assert resp.provider == "mock"
    assert resp.model == "mock-v1"
    assert resp.input_tokens >= 0


def test_mock_llm_fixed_response():
    provider = MockLLMProvider(fixed_response='{"test": true}')
    resp = provider.complete(prompt="anything")
    assert resp.content == '{"test": true}'


def test_mock_transcriber_returns_string():
    t = MockTranscriber()
    result = t.transcribe("/fake/path.ogg")
    assert isinstance(result, str)
    assert len(result) > 0
    assert "/fake/path.ogg" in result


def test_mock_transcriber_provider_name():
    assert MockTranscriber().provider_name == "mock"
