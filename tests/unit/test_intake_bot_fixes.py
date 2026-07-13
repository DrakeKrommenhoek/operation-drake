"""Tests for the four intake-bot fixes:

1. Source URL is written whenever a link is present, regardless of content
   type / classification outcome.
2. Source (how the message arrived) and Source URL (the link, if any) are
   decoupled -- neither influences the other.
3. Actionable is a deterministic post-processing step derived from
   next_action, never a raw model output.
4. A deterministic keyword pre-filter catches meta-noise (confirmation
   checks, bot-directed instructions) before any classifier call, logging
   it to a separate table instead of creating a vault entry.
"""

from __future__ import annotations

import json
import tempfile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from operation_drake.integrations.notion.mock_client import MockNotionClient
from operation_drake.integrations.notion.sync_service import NotionSyncService
from operation_drake.llm.base import LLMResponse
from operation_drake.llm.mock_provider import MockLLMProvider
from operation_drake.models.database import Base, MetaNoiseLogORM
from operation_drake.services.orchestration import OrchestratorService
from operation_drake.transcription.mock_transcriber import MockTranscriber


def _make_orchestrator(tmpdir, llm=None):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = MockNotionClient()
    notion_svc = NotionSyncService(session=session, client=client, database_id="db-test")
    orch = OrchestratorService(
        session=session,
        llm=llm or MockLLMProvider(),
        transcriber=MockTranscriber(),
        artifacts_dir=tmpdir,
        notion_sync_service=notion_svc,
    )
    return orch, client


class _ExplodingLLM(MockLLMProvider):
    """Raises if called at all -- used to prove the keyword pre-filter never
    reaches the model."""

    def complete(self, prompt: str, system: str = "", json_response=None, **kwargs) -> LLMResponse:
        raise AssertionError("LLM should never be called for a pre-filtered message")


class _NotionClassifierOnlyLLM(MockLLMProvider):
    """Returns a fixed Notion-classifier response only for the classifier's
    own prompt (identified by its distinctive vault-category marker) and
    falls back to normal mock behavior for the router/capture/synthesis
    calls that happen earlier in the same pipeline run."""

    def __init__(self, classifier_response: str):
        super().__init__()
        self._classifier_response = classifier_response

    def complete(self, prompt: str, system: str = "", json_response=None, **kwargs) -> LLMResponse:
        if "notion knowledge vault" in prompt.lower():
            return LLMResponse(
                content=self._classifier_response,
                provider="mock",
                model="mock-v1",
            )
        return super().complete(prompt, system=system, json_response=json_response, **kwargs)


# ---------------------------------------------------------------------------
# 1 & 2: Source URL is always written and decoupled from Source / content type
# ---------------------------------------------------------------------------


def test_source_url_written_from_raw_text_regex_fallback():
    with tempfile.TemporaryDirectory() as tmpdir:
        orch, client = _make_orchestrator(tmpdir)
        orch.process(
            channel="telegram",
            raw_text="Business idea, see https://example.com/article for reference",
            sender_id="u1",
        )
        assert len(client.created_pages) == 1
        props = client.created_pages[0]["properties"]
        assert props["Source URL"]["url"] == "https://example.com/article"


def test_source_url_written_from_telegram_text_link_entity_over_raw_text():
    with tempfile.TemporaryDirectory() as tmpdir:
        orch, client = _make_orchestrator(tmpdir)
        entities = [
            {
                "type": "text_link",
                "offset": 0,
                "length": 4,
                "url": "https://real-target.example.com",
            }
        ]
        orch.process(
            channel="telegram",
            raw_text="Read this idea for later",
            sender_id="u1",
            entities=entities,
        )
        props = client.created_pages[0]["properties"]
        assert props["Source URL"]["url"] == "https://real-target.example.com"


def test_source_url_omitted_when_no_link_present():
    with tempfile.TemporaryDirectory() as tmpdir:
        orch, client = _make_orchestrator(tmpdir)
        orch.process(channel="telegram", raw_text="Just a plain idea, no links", sender_id="u1")
        props = client.created_pages[0]["properties"]
        assert "Source URL" not in props


def test_source_url_written_regardless_of_content_type():
    """A link should be written even when the classified content type has
    nothing to do with 'link' or 'article' -- Source URL is independent of
    Content Type."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fixed = json.dumps(
            {
                "project": "Personal Life",
                "content_type": "Journal Entry",
                "title": "Evening reflection",
                "summary": "A personal reflection.",
                "tags": [],
                "actionable": False,
                "next_action": "",
                "capture_context": "Evening Reflection",
                "confidence": 0.9,
                "sync_to_notion": True,
                "notion_status": "Inbox",
            }
        )
        orch, client = _make_orchestrator(tmpdir, llm=_NotionClassifierOnlyLLM(fixed))
        orch.process(
            channel="telegram",
            raw_text="Reflecting tonight, also saw https://example.com/read-later",
            sender_id="u1",
        )
        props = client.created_pages[0]["properties"]
        assert props["Content Type"]["select"]["name"] == "Journal Entry"
        assert props["Source URL"]["url"] == "https://example.com/read-later"


def test_source_field_unaffected_by_presence_of_url():
    """Source describes channel/message_type delivery, not whether a link
    was present -- a plain text message with a URL in it is still
    'Telegram Text', not reclassified as a URL source."""
    with tempfile.TemporaryDirectory() as tmpdir:
        orch, client = _make_orchestrator(tmpdir)
        orch.process(
            channel="telegram",
            raw_text="Some commentary about https://example.com/thing",
            sender_id="u1",
        )
        props = client.created_pages[0]["properties"]
        assert props["Source"]["select"]["name"] == "Telegram Text"
        assert props["Source URL"]["url"] == "https://example.com/thing"


# ---------------------------------------------------------------------------
# 3: Actionable is deterministic, derived from next_action, end to end
# ---------------------------------------------------------------------------


def test_actionable_forced_false_end_to_end_when_next_action_empty_despite_model_true():
    with tempfile.TemporaryDirectory() as tmpdir:
        fixed = json.dumps(
            {
                "project": "Career & Work",
                "content_type": "Action Plan",
                "title": "Follow up",
                "summary": "Some plan.",
                "tags": [],
                "actionable": True,
                "next_action": "",
                "capture_context": "General",
                "confidence": 0.9,
                "sync_to_notion": True,
                "notion_status": "Inbox",
            }
        )
        orch, client = _make_orchestrator(tmpdir, llm=_NotionClassifierOnlyLLM(fixed))
        orch.process(channel="telegram", raw_text="Some plan of action", sender_id="u1")
        props = client.created_pages[0]["properties"]
        assert props["Actionable"]["checkbox"] is False


def test_actionable_forced_true_end_to_end_when_next_action_present_despite_model_false():
    with tempfile.TemporaryDirectory() as tmpdir:
        fixed = json.dumps(
            {
                "project": "Career & Work",
                "content_type": "Action Plan",
                "title": "Follow up",
                "summary": "Some plan.",
                "tags": [],
                "actionable": False,
                "next_action": "Email the recruiter tomorrow",
                "capture_context": "General",
                "confidence": 0.9,
                "sync_to_notion": True,
                "notion_status": "Inbox",
            }
        )
        orch, client = _make_orchestrator(tmpdir, llm=_NotionClassifierOnlyLLM(fixed))
        orch.process(channel="telegram", raw_text="Some plan of action", sender_id="u1")
        props = client.created_pages[0]["properties"]
        assert props["Actionable"]["checkbox"] is True


# ---------------------------------------------------------------------------
# 4: Deterministic meta-noise pre-filter, before any classifier call
# ---------------------------------------------------------------------------


def test_confirmation_seeking_message_is_prefiltered_without_model_call():
    with tempfile.TemporaryDirectory() as tmpdir:
        orch, client = _make_orchestrator(tmpdir, llm=_ExplodingLLM())
        result = orch.process(channel="telegram", raw_text="did that save?", sender_id="u1")
        assert result.status == "meta_noise_logged"
        assert result.task_id == ""
        assert len(client.created_pages) == 0


def test_bot_directed_instruction_is_prefiltered_without_model_call():
    with tempfile.TemporaryDirectory() as tmpdir:
        orch, client = _make_orchestrator(tmpdir, llm=_ExplodingLLM())
        result = orch.process(channel="telegram", raw_text="add my ideas to notion", sender_id="u1")
        assert result.status == "meta_noise_logged"
        assert len(client.created_pages) == 0


def test_prefiltered_message_is_logged_to_meta_noise_log_table_not_inbound_messages():
    from operation_drake.models.database import InboundMessageORM

    with tempfile.TemporaryDirectory() as tmpdir:
        orch, _client = _make_orchestrator(tmpdir, llm=_ExplodingLLM())
        before_inbound = orch._session.query(InboundMessageORM).count()
        orch.process(channel="telegram", raw_text="is that in notion?", sender_id="u1")
        after_inbound = orch._session.query(InboundMessageORM).count()
        assert after_inbound == before_inbound

        logs = orch._session.query(MetaNoiseLogORM).all()
        assert len(logs) == 1
        assert logs[0].category == "confirmation_check"
        assert logs[0].raw_text == "is that in notion?"


def test_genuine_capture_is_not_prefiltered():
    with tempfile.TemporaryDirectory() as tmpdir:
        orch, client = _make_orchestrator(tmpdir)
        result = orch.process(
            channel="telegram", raw_text="Business idea: AI deployment for PE firms", sender_id="u1"
        )
        assert result.status != "meta_noise_logged"
        assert len(client.created_pages) == 1
