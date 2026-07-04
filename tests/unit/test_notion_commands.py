from operation_drake.channels.telegram import _format_result
from operation_drake.services.orchestration import ProcessResult


def _make_result(**kwargs) -> ProcessResult:
    defaults = dict(
        message_id="m1",
        task_id="t1",
        intent="save_note",
        confidence=0.9,
        proposed_action="Save note",
        status="completed",
        approval_required=False,
        clarification_question=None,
        artifact_path="/tmp/test.md",
        result_summary="Note saved.",
    )
    defaults.update(kwargs)
    return ProcessResult(**defaults)


def test_format_result_no_notion_when_status_none():
    r = _make_result()
    text = _format_result(r)
    assert "Notion" not in text
    assert "Project:" not in text


def test_format_result_includes_notion_synced():
    r = _make_result(
        notion_sync_status="synced",
        notion_project="Business Ideas",
        notion_content_type="Idea",
        notion_page_url="https://notion.so/abc123",
    )
    text = _format_result(r)
    assert "Project: Business Ideas" in text
    assert "Type: Idea" in text
    assert "Notion: synced" in text
    assert "https://notion.so/abc123" in text


def test_format_result_notion_updated_shows_synced():
    r = _make_result(
        notion_sync_status="updated",
        notion_project="Ascend",
        notion_content_type="Idea",
    )
    text = _format_result(r)
    assert "Notion: synced" in text


def test_format_result_notion_already_synced_shows_synced():
    r = _make_result(
        notion_sync_status="already_synced",
        notion_project="General",
    )
    text = _format_result(r)
    assert "Notion: synced" in text


def test_format_result_notion_failed_shows_pending():
    r = _make_result(notion_sync_status="failed")
    text = _format_result(r)
    assert "pending" in text.lower()
    assert "Notion" in text


def test_format_result_notion_skipped_not_shown():
    r = _make_result(notion_sync_status="skipped")
    text = _format_result(r)
    assert "Notion" not in text


def test_format_result_notion_disabled_not_shown():
    r = _make_result(notion_sync_status="disabled")
    text = _format_result(r)
    assert "Notion" not in text


def test_format_result_notion_needs_review_note():
    r = _make_result(
        notion_sync_status="synced",
        notion_project="General",
        notion_content_type="General Note",
        notion_needs_review=True,
    )
    text = _format_result(r)
    assert "Needs Review" in text or "uncertain" in text.lower()


def test_format_result_notion_no_url_still_works():
    r = _make_result(
        notion_sync_status="synced",
        notion_project="Ascend",
        notion_content_type="Idea",
        notion_page_url=None,
    )
    text = _format_result(r)
    assert "Project: Ascend" in text
    assert "Notion: synced" in text


def test_format_result_notion_no_project_still_works():
    r = _make_result(
        notion_sync_status="synced",
        notion_project=None,
        notion_content_type=None,
        notion_page_url="https://notion.so/xyz",
    )
    text = _format_result(r)
    assert "Notion: synced" in text
    assert "https://notion.so/xyz" in text
