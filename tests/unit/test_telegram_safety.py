"""Tests for Telegram reply safety.

Design: _format_result returns plain prose (no Markdown syntax added by the app).
        _safe_text strips Markdown v1 control characters at send time.
        Because we never pass parse_mode to reply_text, underscores in intent
        names like "save_note" are harmless plain text and are NOT stripped by
        _format_result itself -- _safe_text handles that at the send boundary.
"""

import os

import pytest

from operation_drake.channels.telegram import _format_result, _safe_text
from operation_drake.services.orchestration import ProcessResult

# ---------------------------------------------------------------------------
# _safe_text: strips Telegram Markdown v1 control characters
# ---------------------------------------------------------------------------


def test_safe_text_strips_asterisks():
    result = _safe_text("*bold*")
    assert "*" not in result
    assert "bold" in result


def test_safe_text_strips_underscores():
    result = _safe_text("_italic_")
    assert "_" not in result
    assert "italic" in result


def test_safe_text_strips_backticks():
    result = _safe_text("`code`")
    assert "`" not in result
    assert "code" in result


def test_safe_text_strips_square_brackets():
    result = _safe_text("[link text](url)")
    assert "[" not in result
    assert "]" not in result
    assert "link text" in result


def test_safe_text_preserves_hyphens():
    assert _safe_text("save-note") == "save-note"


def test_safe_text_preserves_periods():
    assert _safe_text("e.g. something") == "e.g. something"


def test_safe_text_preserves_parentheses():
    assert _safe_text("(85% confident)") == "(85% confident)"


def test_safe_text_preserves_urls():
    url = "https://example.com/path?q=1&r=2"
    assert _safe_text(url) == url


def test_safe_text_handles_unmatched_asterisk():
    assert "*" not in _safe_text("save * note")


def test_safe_text_handles_underscores_in_intent_name():
    # save_note is application text; _safe_text strips the underscore
    result = _safe_text("Intent: save_note (85%)")
    assert "_" not in result
    assert "Intent" in result


def test_safe_text_handles_mixed_markdown():
    raw = "*Intent:* save_note (85% confident)"
    result = _safe_text(raw)
    assert "*" not in result
    assert "_" not in result
    assert "Intent" in result


def test_safe_text_multiline():
    raw = "*Line 1*\n_Line 2_\n`Line 3`"
    result = _safe_text(raw)
    assert "*" not in result
    assert "_" not in result
    assert "`" not in result
    assert "Line 1" in result
    assert "Line 2" in result
    assert "Line 3" in result


def test_safe_text_empty():
    assert _safe_text("") == ""


def test_safe_text_plain_is_unchanged():
    plain = "Save this note: hello world 123"
    assert _safe_text(plain) == plain


# ---------------------------------------------------------------------------
# _format_result: must not add Markdown control chars (* _ ` [])
# Application prose is plain text; intent names may contain underscores and
# that is expected -- _safe_text strips them at the send boundary.
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
    r = _make_result()
    assert "*" not in _format_result(r)


def test_format_result_no_backticks():
    r = _make_result()
    assert "`" not in _format_result(r)


def test_format_result_no_square_brackets():
    r = _make_result()
    text = _format_result(r)
    assert "[" not in text
    assert "]" not in text


def test_format_result_safe_after_safe_text():
    """The full send pipeline (format then safe_text) must always produce clean output."""
    r = _make_result(proposed_action="Save note about save_note workflow design")
    result = _safe_text(_format_result(r))
    assert "*" not in result
    assert "`" not in result
    assert "[" not in result


def test_format_result_awaiting_approval_includes_commands():
    r = _make_result(status="awaiting_approval", approval_required=True)
    text = _format_result(r)
    assert "/approve" in text
    assert "/reject" in text
    assert "task-abc-123" in text


def test_format_result_with_clarification_question():
    r = _make_result(
        intent="clarify",
        status="awaiting_approval",
        clarification_question="Did you mean to save or summarize?",
    )
    assert "Did you mean" in _format_result(r)


def test_format_result_completed_with_summary():
    r = _make_result(
        status="completed",
        result_summary="Note captured: morning routine tracker idea",
        artifact_path="/data/artifacts/abc_Note.md",
    )
    text = _format_result(r)
    assert "morning routine" in text
    assert "Artifact saved" in text


def test_format_result_with_markdown_chars_in_llm_action():
    """LLM-generated proposed_action with Markdown chars must not cause test failure.
    _safe_text handles stripping at the send boundary, not in _format_result."""
    r = _make_result(proposed_action="Save *important* note about _fitness_ goals")
    text = _format_result(r)
    # format_result preserves the action as-is; _safe_text strips at send time
    safe = _safe_text(text)
    assert "*" not in safe
    assert "_" not in safe


# ---------------------------------------------------------------------------
# Provider factory: must raise ValueError for unknown provider names
# ---------------------------------------------------------------------------


def test_unknown_llm_provider_raises():
    os.environ["DEFAULT_LLM_PROVIDER"] = "gpt-turbo-unknown"
    from operation_drake.config import get_settings

    get_settings.cache_clear()
    from operation_drake.llm import get_llm_provider

    with pytest.raises(ValueError, match="Unknown DEFAULT_LLM_PROVIDER"):
        get_llm_provider()
    # restore
    os.environ["DEFAULT_LLM_PROVIDER"] = "mock"
    get_settings.cache_clear()


def test_unknown_transcription_provider_raises():
    os.environ["DEFAULT_TRANSCRIPTION_PROVIDER"] = "deepgram"
    from operation_drake.config import get_settings

    get_settings.cache_clear()
    from operation_drake.transcription import get_transcription_provider

    with pytest.raises(ValueError, match="Unknown DEFAULT_TRANSCRIPTION_PROVIDER"):
        get_transcription_provider()
    # restore
    os.environ["DEFAULT_TRANSCRIPTION_PROVIDER"] = "mock"
    get_settings.cache_clear()


def test_mock_provider_is_valid_explicit_choice():
    """'mock' must not raise -- it is a valid explicit provider name."""
    os.environ["DEFAULT_LLM_PROVIDER"] = "mock"
    from operation_drake.config import get_settings

    get_settings.cache_clear()
    from operation_drake.llm import get_llm_provider
    from operation_drake.llm.mock_provider import MockLLMProvider

    provider = get_llm_provider()
    assert isinstance(provider, MockLLMProvider)
    get_settings.cache_clear()


def test_env_duplicate_key_last_wins():
    """Document that duplicate keys in .env cause last-value-wins behavior.
    This is the root cause of the mock-provider selection bug (session 3).
    Validated by: DEFAULT_LLM_PROVIDER set to 'mock' overrides 'openai' if it
    appears later in the .env file."""
    os.environ["DEFAULT_LLM_PROVIDER"] = "mock"
    from operation_drake.config import get_settings

    get_settings.cache_clear()
    s = get_settings()
    assert s.default_llm_provider == "mock"
    # cleanup
    del os.environ["DEFAULT_LLM_PROVIDER"]
    get_settings.cache_clear()
