from operation_drake.llm.base import LLMProvider, LLMResponse

_DEFAULT_ROUTER = '{"primary_intent":"save_note","secondary_intents":[],"confidence":0.85,"proposed_action":"Save this as a note","approval_required":false,"clarification_question":null,"rationale_summary":"Message appears to be a note or idea to capture."}'
_DEFAULT_CAPTURE = '{"title":"Captured Note","project":null,"tags":["idea"],"summary":"A note captured from user input.","action_items":[]}'
_DEFAULT_SYNTHESIS = '{"title":"Summary","summary":"Key points extracted from the provided content.","key_points":["Main point identified"],"action_items":[],"questions":[],"next_steps":[]}'
_DEFAULT_META_NOISE = '{"category":"capture","confidence":90,"answer":"","rationale":"Looks like capture-worthy content."}'


class MockLLMProvider(LLMProvider):
    provider_name = "mock"
    model_name = "mock-v1"

    def __init__(self, fixed_response: str | None = None):
        self._fixed = fixed_response

    def complete(
        self, prompt: str, system: str = "", json_response: str | None = None, **kwargs
    ) -> LLMResponse:
        if self._fixed:
            content = self._fixed
        elif json_response:
            content = json_response
        elif "triage" in prompt.lower():
            content = _DEFAULT_META_NOISE
        elif (
            "route" in prompt.lower() or "intent" in prompt.lower() or "classify" in prompt.lower()
        ):
            content = _DEFAULT_ROUTER
        elif "capture" in prompt.lower() or "metadata" in prompt.lower():
            content = _DEFAULT_CAPTURE
        else:
            content = _DEFAULT_SYNTHESIS
        return LLMResponse(
            content=content, provider="mock", model="mock-v1", input_tokens=10, output_tokens=20
        )
