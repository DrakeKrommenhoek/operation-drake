import json

from operation_drake.integrations.notion.classifier import NotionClassifier
from operation_drake.llm.mock_provider import MockLLMProvider


def _valid_json(**overrides) -> str:
    base = {
        "project": "Business Ideas",
        "content_type": "Idea",
        "title": "AI deployment service for PE firms",
        "summary": "An idea for an AI agent deployment service targeting small PE firms.",
        "tags": ["AI", "PE", "startup"],
        "actionable": False,
        "next_action": "",
        "capture_context": "General",
        "confidence": 0.92,
        "sync_to_notion": True,
        "notion_status": "Inbox",
    }
    base.update(overrides)
    return json.dumps(base)


def _clf(response: str) -> NotionClassifier:
    return NotionClassifier(llm=MockLLMProvider(fixed_response=response))


def test_classify_returns_notion_classification():
    clf = _clf(_valid_json())
    result = clf.classify("Business idea: AI deployment service for PE firms")
    assert result.project == "Business Ideas"
    assert result.content_type == "Idea"
    assert result.confidence == 0.92
    assert result.notion_status == "Inbox"
    assert result.sync_to_notion is True
    assert result.title == "AI deployment service for PE firms"


def test_classify_low_confidence_sets_needs_review():
    clf = _clf(
        _valid_json(
            project="General", content_type="General Note", confidence=0.55, notion_status="Inbox"
        )
    )
    result = clf.classify("some unclear content")
    assert result.notion_status == "Needs Review"
    assert result.project == "General"


def test_classify_low_confidence_threshold_boundary():
    # exactly at threshold → Inbox
    clf = _clf(_valid_json(confidence=0.70))
    result = clf.classify("content")
    assert result.notion_status == "Inbox"

    # just below → Needs Review
    clf2 = _clf(_valid_json(confidence=0.69))
    result2 = clf2.classify("content")
    assert result2.notion_status == "Needs Review"


def test_classify_explicit_no_sync():
    clf = _clf(_valid_json(sync_to_notion=False, confidence=0.95))
    result = clf.classify("Do not save this to Notion. Private thought.")
    assert result.sync_to_notion is False


def test_classify_notion_status_needs_review_from_llm():
    clf = _clf(_valid_json(confidence=0.95, notion_status="Needs Review"))
    result = clf.classify("ambiguous")
    assert result.notion_status == "Needs Review"


def test_classify_invalid_project_falls_back_to_general():
    clf = _clf(_valid_json(project="NotARealProject"))
    result = clf.classify("something")
    assert result.project == "General"


def test_classify_invalid_content_type_falls_back():
    clf = _clf(_valid_json(content_type="XYZType"))
    result = clf.classify("something")
    assert result.content_type == "General Note"


def test_classify_invalid_context_falls_back():
    clf = _clf(_valid_json(capture_context="MoonBase"))
    result = clf.classify("something")
    assert result.capture_context == "General"


def test_classify_llm_failure_returns_safe_default():
    # _parse_json returns {} silently on invalid JSON, defaults kick in
    clf = NotionClassifier(llm=MockLLMProvider(fixed_response="not valid json {{{{"))
    result = clf.classify("test content")
    assert result.notion_status == "Needs Review"  # confidence 0.5 < 0.70 threshold
    assert result.project == "General"
    assert result.content_type == "General Note"


def test_classify_tags_capped_at_ten():
    many_tags = [f"tag{i}" for i in range(15)]
    clf = _clf(_valid_json(tags=many_tags))
    result = clf.classify("something with many tags")
    assert len(result.tags) <= 10


def test_classify_title_capped_at_200():
    clf = _clf(_valid_json(title="x" * 300))
    result = clf.classify("something")
    assert len(result.title) <= 200


def test_classify_the_answer_movement():
    clf = _clf(
        _valid_json(
            project="The Answer Movement",
            content_type="Idea",
            title="Timer breathing exercise for challenge",
            confidence=0.93,
        )
    )
    result = clf.classify("Answer Movement idea: add timer breathing exercise")
    assert result.project == "The Answer Movement"
    assert result.content_type == "Idea"


# ---------------------------------------------------------------------------
# Actionable is derived deterministically from next_action, never trusted
# from the model's own boolean.
# ---------------------------------------------------------------------------


def test_classify_actionable_true_when_model_says_false_but_next_action_present():
    clf = _clf(_valid_json(actionable=False, next_action="Follow up with the accountant"))
    result = clf.classify("something")
    assert result.actionable is True
    assert result.next_action == "Follow up with the accountant"


def test_classify_actionable_false_when_model_says_true_but_next_action_empty():
    clf = _clf(_valid_json(actionable=True, next_action=""))
    result = clf.classify("something")
    assert result.actionable is False


def test_classify_actionable_false_when_next_action_is_only_whitespace():
    clf = _clf(_valid_json(actionable=True, next_action="   "))
    result = clf.classify("something")
    assert result.actionable is False


def test_classify_prework_drive_context():
    clf = _clf(
        _valid_json(
            project="Career & Work",
            content_type="Workday Check-in",
            capture_context="Pre-work Drive",
            confidence=0.88,
        )
    )
    result = clf.classify(
        "On the drive to work, I want to focus on finishing the retention analysis"
    )
    assert result.capture_context == "Pre-work Drive"
    assert result.content_type == "Workday Check-in"
