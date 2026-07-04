from datetime import datetime, timezone

from operation_drake.integrations.notion.mapper import build_properties, channel_to_source
from operation_drake.integrations.notion.models import NotionClassification


def _ts() -> datetime:
    return datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)


def test_channel_to_source_telegram_text():
    assert channel_to_source("telegram", "text") == "Telegram Text"


def test_channel_to_source_telegram_voice():
    assert channel_to_source("telegram", "voice") == "Telegram Voice"


def test_channel_to_source_telegram_forwarded():
    assert channel_to_source("telegram", "forwarded") == "Telegram Forward"


def test_channel_to_source_unknown_falls_back():
    assert channel_to_source("chatgpt", "voice") == "Other"


def test_build_properties_name():
    c = NotionClassification(title="My Idea", task_id="t1")
    props = build_properties(c, _ts(), "Telegram Text")
    assert props["Name"]["title"][0]["text"]["content"] == "My Idea"


def test_build_properties_project():
    c = NotionClassification(project="Ascend", title="x", task_id="t1")
    props = build_properties(c, _ts(), "Telegram Text")
    assert props["Project"]["select"]["name"] == "Ascend"


def test_build_properties_content_type():
    c = NotionClassification(content_type="Idea", title="x", task_id="t1")
    props = build_properties(c, _ts(), "Telegram Text")
    assert props["Content Type"]["select"]["name"] == "Idea"


def test_build_properties_actionable_checkbox():
    c = NotionClassification(actionable=True, title="x", task_id="t1")
    props = build_properties(c, _ts(), "Telegram Text")
    assert props["Actionable"]["checkbox"] is True


def test_build_properties_actionable_false():
    c = NotionClassification(actionable=False, title="x", task_id="t1")
    props = build_properties(c, _ts(), "Telegram Text")
    assert props["Actionable"]["checkbox"] is False


def test_build_properties_source_url_omitted_when_none():
    c = NotionClassification(title="x", task_id="t1", source_url=None)
    props = build_properties(c, _ts(), "Telegram Text")
    assert "Source URL" not in props


def test_build_properties_source_url_included_when_set():
    c = NotionClassification(title="x", task_id="t1", source_url="https://example.com")
    props = build_properties(c, _ts(), "Telegram Text")
    assert props["Source URL"]["url"] == "https://example.com"


def test_build_properties_long_title_truncated():
    c = NotionClassification(title="x" * 3000, task_id="t1")
    props = build_properties(c, _ts(), "Telegram Text")
    content = props["Name"]["title"][0]["text"]["content"]
    assert len(content) <= 2000


def test_build_properties_task_id_stored():
    c = NotionClassification(title="x", task_id="task-abc-123")
    props = build_properties(c, _ts(), "Telegram Text")
    assert props["D.R.A.K.E. Task ID"]["rich_text"][0]["text"]["content"] == "task-abc-123"


def test_build_properties_artifact_id_stored():
    c = NotionClassification(title="x", task_id="t1", artifact_id="art-999")
    props = build_properties(c, _ts(), "Telegram Text")
    assert props["D.R.A.K.E. Artifact ID"]["rich_text"][0]["text"]["content"] == "art-999"


def test_build_properties_confidence_number():
    c = NotionClassification(title="x", task_id="t1", confidence=0.87654)
    props = build_properties(c, _ts(), "Telegram Text")
    assert props["Confidence"]["number"] == 0.8765


def test_build_properties_tags_multi_select():
    c = NotionClassification(title="x", task_id="t1", tags=["AI", "PE"])
    props = build_properties(c, _ts(), "Telegram Text")
    names = [t["name"] for t in props["Tags"]["multi_select"]]
    assert "AI" in names and "PE" in names


def test_build_properties_sync_status_synced():
    c = NotionClassification(title="x", task_id="t1")
    props = build_properties(c, _ts(), "Telegram Text")
    assert props["Sync Status"]["select"]["name"] == "Synced"


def test_build_properties_captured_at_iso():
    c = NotionClassification(title="x", task_id="t1")
    props = build_properties(c, _ts(), "Telegram Text")
    assert "2026-07-04" in props["Captured At"]["date"]["start"]
