from __future__ import annotations

from operation_drake.integrations.notion.models import NotionClassification

_BLOCK_TEXT_MAX = 2000


def _text_chunks(content: str) -> list[str]:
    chunks = []
    while content:
        chunks.append(content[:_BLOCK_TEXT_MAX])
        content = content[_BLOCK_TEXT_MAX:]
    return chunks


def _paragraph(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [{"type": "text", "text": {"content": text[:_BLOCK_TEXT_MAX]}}]},
    }


def _heading(text: str, level: int = 2) -> dict:
    h = f"heading_{level}"
    return {
        "object": "block",
        "type": h,
        h: {"rich_text": [{"type": "text", "text": {"content": text[:_BLOCK_TEXT_MAX]}}]},
    }


def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def _todo(text: str) -> dict:
    return {
        "object": "block",
        "type": "to_do",
        "to_do": {
            "rich_text": [{"type": "text", "text": {"content": text[:_BLOCK_TEXT_MAX]}}],
            "checked": False,
        },
    }


def _paragraphs_for(content: str) -> list[dict]:
    return [_paragraph(chunk) for chunk in _text_chunks(content) if chunk.strip()]


def build_body(classification: NotionClassification) -> list[dict]:
    blocks: list[dict] = []

    if classification.summary:
        blocks.append(_heading("Summary"))
        blocks.extend(_paragraphs_for(classification.summary))

    if classification.actionable and classification.next_action:
        blocks.append(_divider())
        blocks.append(_heading("Action Items"))
        for line in classification.next_action.splitlines():
            line = line.strip()
            if line:
                blocks.append(_todo(line))

    blocks.append(_divider())
    blocks.append(_heading("D.R.A.K.E. Metadata", level=3))
    meta_lines = [
        f"Task ID: {classification.task_id}",
        f"Artifact ID: {classification.artifact_id or 'none'}",
        f"Project: {classification.project}",
        f"Content Type: {classification.content_type}",
        f"Capture Context: {classification.capture_context}",
        f"Confidence: {classification.confidence:.0%}",
    ]
    blocks.append(_paragraph("\n".join(meta_lines)))

    return blocks
