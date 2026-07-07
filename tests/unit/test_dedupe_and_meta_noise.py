from __future__ import annotations

import tempfile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from operation_drake.ingestion.normalizer import compute_message_hash
from operation_drake.llm.base import LLMResponse
from operation_drake.llm.mock_provider import MockLLMProvider
from operation_drake.models.database import Base
from operation_drake.services.orchestration import OrchestratorService
from operation_drake.transcription.mock_transcriber import MockTranscriber


def _make_orchestrator(tmpdir, llm=None):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    orch = OrchestratorService(
        session=session,
        llm=llm or MockLLMProvider(),
        transcriber=MockTranscriber(),
        artifacts_dir=tmpdir,
    )
    return orch


class _LowConfidenceThenNormalLLM(MockLLMProvider):
    """Returns a low-confidence capture verdict for the meta-noise triage
    call, and falls back to normal mock behavior for every other call."""

    def complete(self, prompt: str, system: str = "", json_response=None, **kwargs) -> LLMResponse:
        if "triage" in prompt.lower():
            return LLMResponse(
                content='{"category":"capture","confidence":10,"answer":"","rationale":"unsure"}',
                provider="mock",
                model="mock-v1",
            )
        return super().complete(prompt, system=system, json_response=json_response, **kwargs)


# ---------------------------------------------------------------------------
# compute_message_hash
# ---------------------------------------------------------------------------


def test_compute_message_hash_is_case_and_whitespace_insensitive():
    a = compute_message_hash("Hello   World")
    b = compute_message_hash("hello world")
    c = compute_message_hash("  hello\nworld  ")
    assert a == b == c


def test_compute_message_hash_differs_for_different_content():
    assert compute_message_hash("note one") != compute_message_hash("note two")


# ---------------------------------------------------------------------------
# Dedupe via OrchestratorService.process
# ---------------------------------------------------------------------------


def test_duplicate_message_is_skipped_and_flagged():
    with tempfile.TemporaryDirectory() as tmpdir:
        orch = _make_orchestrator(tmpdir)
        first = orch.process(
            channel="telegram", raw_text="Save this note about PE firms", sender_id="u1"
        )
        assert first.status == "completed"

        second = orch.process(
            channel="telegram", raw_text="Save this note about PE firms", sender_id="u1"
        )
        assert second.status == "duplicate"
        assert "Already captured" in second.result_summary


def test_reworded_duplicate_still_matches_after_case_and_whitespace_normalization():
    with tempfile.TemporaryDirectory() as tmpdir:
        orch = _make_orchestrator(tmpdir)
        orch.process(channel="telegram", raw_text="Save this note about PE firms", sender_id="u1")
        second = orch.process(
            channel="telegram", raw_text="  save this note about pe firms  ", sender_id="u1"
        )
        assert second.status == "duplicate"


def test_different_messages_are_not_flagged_as_duplicate():
    with tempfile.TemporaryDirectory() as tmpdir:
        orch = _make_orchestrator(tmpdir)
        orch.process(channel="telegram", raw_text="Save this note about PE firms", sender_id="u1")
        second = orch.process(
            channel="telegram", raw_text="A completely different idea", sender_id="u1"
        )
        assert second.status != "duplicate"


# ---------------------------------------------------------------------------
# Meta-noise filter: question / command / low-confidence gates
# ---------------------------------------------------------------------------


def test_question_message_is_answered_and_creates_no_task():
    with tempfile.TemporaryDirectory() as tmpdir:
        llm = MockLLMProvider(
            fixed_response='{"category":"question","confidence":95,'
            '"answer":"Yes, it saved fine.","rationale":"asking about status"}'
        )
        orch = _make_orchestrator(tmpdir, llm=llm)
        result = orch.process(
            channel="telegram", raw_text="did that last note save?", sender_id="u1"
        )
        assert result.status == "answered"
        assert result.result_summary == "Yes, it saved fine."
        assert result.task_id == ""


def test_command_message_returns_hint_and_creates_no_task():
    with tempfile.TemporaryDirectory() as tmpdir:
        llm = MockLLMProvider(
            fixed_response='{"category":"command","confidence":80,"answer":"","rationale":"ack"}'
        )
        orch = _make_orchestrator(tmpdir, llm=llm)
        result = orch.process(channel="telegram", raw_text="ok thanks", sender_id="u1")
        assert result.status == "command_hint"
        assert "/done" in result.result_summary
        assert result.task_id == ""


def test_low_confidence_capture_prompts_confirmation():
    with tempfile.TemporaryDirectory() as tmpdir:
        orch = _make_orchestrator(tmpdir, llm=_LowConfidenceThenNormalLLM())
        result = orch.process(
            channel="telegram", raw_text="hmm not sure about this", sender_id="u1"
        )
        assert result.status == "awaiting_capture_confirmation"
        assert result.task_id == ""


def test_low_confidence_capture_completes_on_yes():
    with tempfile.TemporaryDirectory() as tmpdir:
        orch = _make_orchestrator(tmpdir, llm=_LowConfidenceThenNormalLLM())
        orch.process(channel="telegram", raw_text="hmm not sure about this", sender_id="u1")
        confirmed = orch.process(channel="telegram", raw_text="y", sender_id="u1")
        assert confirmed.status in ("completed", "awaiting_approval")


def test_low_confidence_capture_discarded_on_no():
    with tempfile.TemporaryDirectory() as tmpdir:
        orch = _make_orchestrator(tmpdir, llm=_LowConfidenceThenNormalLLM())
        orch.process(channel="telegram", raw_text="hmm not sure about this", sender_id="u1")
        discarded = orch.process(channel="telegram", raw_text="n", sender_id="u1")
        assert discarded.status == "discarded"


def test_voice_message_skips_meta_noise_gate():
    llm = MockLLMProvider(
        fixed_response='{"category":"question","confidence":95,"answer":"no","rationale":"x"}'
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        orch = _make_orchestrator(tmpdir, llm=llm)
        result = orch.process(
            channel="telegram",
            raw_text="[Voice note]",
            message_type="voice",
            sender_id="u1",
            attachment_path="/fake/voice.ogg",
        )
        assert result.status != "answered"
