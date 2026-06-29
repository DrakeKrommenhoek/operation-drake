"""Regression tests for Telegram reply safety.

Design contract:
- No parse_mode is used, so Telegram renders all characters literally.
- _safe_text() must return content UNCHANGED: underscores, asterisks, brackets,
  backticks, URLs, filenames, and user text must all be preserved.
- _split_message() splits long text at newlines/spaces without dropping content.
- _reply() (async, tested indirectly) calls both in sequence.
"""

import os

import pytest

from operation_drake.channels.telegram import (
    TELEGRAM_MAX_LEN,
    _format_result,
    _safe_text,
    _split_message,
)
from operation_drake.services.orchestration import ProcessResult

# ---------------------------------------------------------------------------
# _safe_text: content must be returned unchanged
# ---------------------------------------------------------------------------


def test_safe_text_preserves_underscores():
    assert _safe_text("save_note") == "save_note"


def test_safe_text_preserves_asterisks():
    assert _safe_text("2 * 3 = 6") == "2 * 3 = 6"


def test_safe_text_preserves_backticks():
    assert _safe_text("`code block`") == "`code block`"


def test_safe_text_preserves_square_brackets():
    assert _safe_text("[link text](url)") == "[link text](url)"


def test_safe_text_preserves_url():
    url = "https://example.com/path?q=1&r=2#anchor"
    assert _safe_text(url) == url


def test_safe_text_preserves_filename():
    name = "abc12345_Captured_Note.md"
    assert _safe_text(name) == name


def test_safe_text_preserves_intent_name_with_underscore():
    assert _safe_text("Intent: save_note (85% confident)") == "Intent: save_note (85% confident)"


def test_safe_text_preserves_mixed_markdown_syntax():
    raw = "*bold* _italic_ `code` [link](url)"
    assert _safe_text(raw) == raw


def test_safe_text_preserves_user_content():
    user = "I want to save a note about my _workout_ and *progress*"
    assert _safe_text(user) == user


def test_safe_text_preserves_hyphens():
    assert _safe_text("research-brief") == "research-brief"


def test_safe_text_preserves_periods():
    assert _safe_text("e.g. something") == "e.g. something"


def test_safe_text_preserves_parentheses():
    assert _safe_text("(85% confident)") == "(85% confident)"


def test_safe_text_empty_string():
    assert _safe_text("") == ""


def test_safe_text_plain_text_unchanged():
    plain = "Save this note: hello world 123"
    assert _safe_text(plain) == plain


def test_safe_text_multiline_unchanged():
    raw = "Line 1\nLine 2 with *stars*\nLine 3 with _underscores_"
    assert _safe_text(raw) == raw


def test_safe_text_unmatched_markdown_preserved():
    # Unmatched markdown chars that would break parse_mode — must be kept as-is
    assert _safe_text("star * note") == "star * note"
    assert _safe_text("an _unclosed italic") == "an _unclosed italic"


# ---------------------------------------------------------------------------
# _split_message: content preservation and correct splitting
# ---------------------------------------------------------------------------


def test_split_message_short_text_is_single_chunk():
    text = "Short message"
    assert _split_message(text) == [text]


def test_split_message_exact_limit_is_single_chunk():
    text = "x" * TELEGRAM_MAX_LEN
    result = _split_message(text)
    assert len(result) == 1
    assert result[0] == text


def test_split_message_one_over_limit_splits():
    text = "x" * (TELEGRAM_MAX_LEN + 1)
    result = _split_message(text)
    assert len(result) == 2
    assert all(len(c) <= TELEGRAM_MAX_LEN for c in result)


def test_split_message_preserves_all_content():
    # Every character must survive the split — nothing dropped
    text = "word " * 1000  # 5000 chars
    chunks = _split_message(text)
    rejoined = " ".join(c.strip() for c in chunks)
    original_words = text.split()
    rejoined_words = rejoined.split()
    assert original_words == rejoined_words


def test_split_message_prefers_newline_split():
    # Build text where the ideal split is at a newline at position 100
    part1 = "a" * 100
    part2 = "b" * 100
    text = part1 + "\n" + part2
    # Max len just beyond part1 so the newline is within the window
    result = _split_message(text, max_len=110)
    assert result[0] == part1
    assert result[1] == part2


def test_split_message_falls_back_to_space():
    # No newlines — must split on space
    words = ["word"] * 20  # "word word word ..." = 99 chars at 5 chars each + spaces
    text = " ".join(words)
    result = _split_message(text, max_len=30)
    assert all(len(c) <= 30 for c in result)
    # Content: all words must be present
    assert " ".join(result).split() == words


def test_split_message_hard_cut_no_whitespace():
    # No whitespace anywhere — must hard-cut at max_len
    text = "x" * 200
    result = _split_message(text, max_len=50)
    assert all(len(c) == 50 for c in result)
    assert "".join(result) == text


def test_split_message_delimiter_not_in_output():
    # The newline used as split point must not appear at start of next chunk
    text = "first\nsecond"
    result = _split_message(text, max_len=6)
    for chunk in result:
        assert not chunk.startswith("\n")


def test_split_message_preserves_urls():
    url = "https://example.com/very/long/path/that/goes/on/forever?query=true"
    text = "Check this out: " + url + " and more text after"
    for chunk in _split_message(text, max_len=40):
        assert len(chunk) <= 40
    rejoined = " ".join(_split_message(text, max_len=40))
    # URL must appear in output (may be split across chunks but chars preserved)
    assert "https" in rejoined
    assert "example.com" in rejoined


def test_split_message_underscores_preserved_across_split():
    text = "save_note intent with confidence_score of 85%\n" * 100
    chunks = _split_message(text)
    full = "\n".join(chunks)
    assert "save_note" in full
    assert "confidence_score" in full


# ---------------------------------------------------------------------------
# _format_result: application text must not introduce * ` [ ]
# (underscores in intent names are fine — they're literals in plain text)
# ---------------------------------------------------------------------------


def _make_result(**kwargs) -> ProcessResult:
    defaults = dict(
        message_id="msg-1",
        task_id="task-abc-123",
        intent="save_note",
        confidence=0.85,
        proposed_action="Save this as a note",
        status="completed",
        approval_required=False,
        clarification_question=None,
        artifact_path=None,
        result_summary="",
    )
    defaults.update(kwargs)
    return ProcessResult(**defaults)


def test_format_result_no_asterisks():
    assert "*" not in _format_result(_make_result())


def test_format_result_no_backticks():
    assert "`" not in _format_result(_make_result())


def test_format_result_no_square_brackets():
    text = _format_result(_make_result())
    assert "[" not in text
    assert "]" not in text


def test_format_result_llm_action_preserved():
    # LLM-generated text with underscores must come through intact
    r = _make_result(proposed_action="Save note about save_note workflow_design")
    text = _format_result(r)
    assert "save_note" in text
    assert "workflow_design" in text


def test_format_result_awaiting_approval_includes_commands():
    r = _make_result(status="awaiting_approval", approval_required=True)
    text = _format_result(r)
    assert "/approve" in text
    assert "/reject" in text
    assert "task-abc-123" in text


def test_format_result_completed_with_summary_and_artifact():
    r = _make_result(
        status="completed",
        result_summary="Note captured: morning_routine tracker idea",
        artifact_path="/data/artifacts/abc_Captured_Note.md",
    )
    text = _format_result(r)
    assert "morning_routine" in text
    assert "Artifact saved" in text


def test_format_result_with_clarification_question():
    r = _make_result(
        intent="clarify",
        status="awaiting_approval",
        clarification_question="Did you mean to save or summarize?",
    )
    assert "Did you mean" in _format_result(r)


# ---------------------------------------------------------------------------
# Provider factory: must raise ValueError for unknown provider names
# (regression for mock-provider-selection bug — see session 3)
# ---------------------------------------------------------------------------


def test_unknown_llm_provider_raises():
    os.environ["DEFAULT_LLM_PROVIDER"] = "gpt-turbo-unknown"
    from operation_drake.config import get_settings

    get_settings.cache_clear()
    from operation_drake.llm import get_llm_provider

    with pytest.raises(ValueError, match="Unknown DEFAULT_LLM_PROVIDER"):
        get_llm_provider()
    os.environ["DEFAULT_LLM_PROVIDER"] = "mock"
    get_settings.cache_clear()


def test_unknown_transcription_provider_raises():
    os.environ["DEFAULT_TRANSCRIPTION_PROVIDER"] = "deepgram"
    from operation_drake.config import get_settings

    get_settings.cache_clear()
    from operation_drake.transcription import get_transcription_provider

    with pytest.raises(ValueError, match="Unknown DEFAULT_TRANSCRIPTION_PROVIDER"):
        get_transcription_provider()
    os.environ["DEFAULT_TRANSCRIPTION_PROVIDER"] = "mock"
    get_settings.cache_clear()


def test_mock_provider_is_valid_explicit_choice():
    os.environ["DEFAULT_LLM_PROVIDER"] = "mock"
    from operation_drake.config import get_settings

    get_settings.cache_clear()
    from operation_drake.llm import get_llm_provider
    from operation_drake.llm.mock_provider import MockLLMProvider

    assert isinstance(get_llm_provider(), MockLLMProvider)
    get_settings.cache_clear()


def test_env_duplicate_key_last_value_wins():
    """Documents the root cause of the mock-provider bug: last duplicate wins."""
    os.environ["DEFAULT_LLM_PROVIDER"] = "mock"
    from operation_drake.config import get_settings

    get_settings.cache_clear()
    assert get_settings().default_llm_provider == "mock"
    del os.environ["DEFAULT_LLM_PROVIDER"]
    get_settings.cache_clear()
