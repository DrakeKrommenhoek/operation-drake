from __future__ import annotations

from operation_drake.agents.meta_noise import MetaNoiseFilterAgent, keyword_prefilter
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


# ---------------------------------------------------------------------------
# keyword_prefilter: deterministic regex triage, no model call involved
# ---------------------------------------------------------------------------


def test_prefilter_matches_confirmation_seeking():
    result = keyword_prefilter("did that save?")
    assert result is not None
    category, _pattern = result
    assert category == "confirmation_check"


def test_prefilter_matches_is_that_in_notion():
    result = keyword_prefilter("is that in notion yet?")
    assert result is not None
    assert result[0] == "confirmation_check"


def test_prefilter_matches_bot_directed_instruction():
    result = keyword_prefilter("add my ideas to notion")
    assert result is not None
    assert result[0] == "bot_instruction"


def test_prefilter_matches_put_in_notion_instruction():
    result = keyword_prefilter("put this in notion please")
    assert result is not None
    assert result[0] == "bot_instruction"


def test_prefilter_returns_none_for_genuine_capture():
    assert keyword_prefilter("Business idea: AI deployment service for PE firms") is None


def test_prefilter_is_case_insensitive():
    result = keyword_prefilter("DID THAT SAVE?")
    assert result is not None
    assert result[0] == "confirmation_check"


def test_prefilter_matches_multi_object_instruction_within_one_clause():
    """A single imperative sentence listing several objects should still
    match -- the bounded wildcard must not be so tight it breaks this."""
    result = keyword_prefilter(
        "add my grocery list AND my business idea about pricing AND some other stuff to notion"
    )
    assert result is not None
    assert result[0] == "bot_instruction"


# ---------------------------------------------------------------------------
# Regression tests: realistic genuine-capture messages that must NOT be
# caught by the deterministic pre-filter, despite superficially resembling
# the confirmation/instruction phrasing above.
# ---------------------------------------------------------------------------


def test_prefilter_does_not_match_into_notion_used_as_a_concept_not_the_app():
    text = (
        "Add my idea about tiered pricing into notion of freemium models -- worth researching more."
    )
    assert keyword_prefilter(text) is None


def test_prefilter_does_not_match_notion_possessive():
    text = (
        "Is this in Notion's roadmap for next quarter? Might be worth a "
        "deeper dive for the Ascend project."
    )
    assert keyword_prefilter(text) is None


def test_prefilter_does_not_match_saved_by_the_bell_idiom():
    text = (
        "Was that saved by the bell moment at the end of the game the craziest finish this season?"
    )
    assert keyword_prefilter(text) is None


def test_prefilter_does_not_match_into_notion_after_a_bot_verb():
    text = (
        "Can you put my thoughts together, I keep going back into notion of "
        "retirement daydreaming and not sure what to do with it"
    )
    assert keyword_prefilter(text) is None


def test_prefilter_does_not_match_instruction_tacked_onto_unrelated_content():
    """The instruction phrase is real, but it's appended after a full,
    independent clause with its own subject and verb -- the message as a
    whole is substantive content, not pure bot-directed noise, so it should
    reach the classifier rather than being logged and discarded outright."""
    text = (
        "Let's sync these calendars up first, then I want to talk through my "
        "business idea for the PE recruiting tool -- can you save that to "
        "Notion once I'm done explaining?"
    )
    assert keyword_prefilter(text) is None
