from operation_drake.integrations.notion.body_builder import _text_chunks, build_body
from operation_drake.integrations.notion.models import NotionClassification


def test_text_chunks_short_content():
    result = _text_chunks("hello")
    assert result == ["hello"]


def test_text_chunks_long_content_splits():
    long = "x" * 5000
    chunks = _text_chunks(long)
    assert len(chunks) == 3
    assert all(len(c) <= 2000 for c in chunks)
    assert "".join(chunks) == long


def test_text_chunks_empty_string():
    assert _text_chunks("") == []


def test_build_body_contains_summary_heading():
    c = NotionClassification(title="T", task_id="t1", summary="This is a summary.")
    blocks = build_body(c)
    heading_blocks = [b for b in blocks if b["type"] == "heading_2"]
    heading_texts = [
        b["heading_2"]["rich_text"][0]["text"]["content"] for b in heading_blocks
    ]
    assert "Summary" in heading_texts


def test_build_body_summary_paragraph():
    c = NotionClassification(title="T", task_id="t1", summary="Key insight here.")
    blocks = build_body(c)
    paragraphs = [
        b["paragraph"]["rich_text"][0]["text"]["content"]
        for b in blocks if b["type"] == "paragraph"
    ]
    all_text = " ".join(paragraphs)
    assert "Key insight here" in all_text


def test_build_body_contains_metadata():
    c = NotionClassification(title="T", task_id="task-xyz", project="Ascend")
    blocks = build_body(c)
    all_text = " ".join(
        b.get("paragraph", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "")
        for b in blocks if b["type"] == "paragraph"
    )
    assert "task-xyz" in all_text
    assert "Ascend" in all_text


def test_build_body_action_items_use_todo_blocks():
    c = NotionClassification(
        title="T", task_id="t1",
        actionable=True,
        next_action="Call mom\nUpdate docs",
    )
    blocks = build_body(c)
    todo_blocks = [b for b in blocks if b["type"] == "to_do"]
    assert len(todo_blocks) == 2


def test_build_body_no_action_items_when_not_actionable():
    c = NotionClassification(title="T", task_id="t1", actionable=False, next_action="")
    blocks = build_body(c)
    todo_blocks = [b for b in blocks if b["type"] == "to_do"]
    assert len(todo_blocks) == 0


def test_build_body_no_todo_when_actionable_but_no_next_action():
    c = NotionClassification(title="T", task_id="t1", actionable=True, next_action="")
    blocks = build_body(c)
    todo_blocks = [b for b in blocks if b["type"] == "to_do"]
    assert len(todo_blocks) == 0


def test_build_body_long_summary_chunked():
    c = NotionClassification(title="T", task_id="t1", summary="x" * 5000)
    blocks = build_body(c)
    paragraphs = [b for b in blocks if b["type"] == "paragraph"]
    for p in paragraphs:
        text = p["paragraph"]["rich_text"][0]["text"]["content"]
        assert len(text) <= 2000


def test_build_body_has_divider():
    c = NotionClassification(title="T", task_id="t1", summary="s")
    blocks = build_body(c)
    dividers = [b for b in blocks if b["type"] == "divider"]
    assert len(dividers) >= 1


def test_build_body_no_summary_skips_summary_section():
    c = NotionClassification(title="T", task_id="t1", summary="")
    blocks = build_body(c)
    heading_texts = [
        b.get(b["type"], {}).get("rich_text", [{}])[0].get("text", {}).get("content", "")
        for b in blocks if b["type"].startswith("heading_")
    ]
    assert "Summary" not in heading_texts
