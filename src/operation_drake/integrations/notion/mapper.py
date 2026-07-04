from __future__ import annotations

from datetime import datetime

from operation_drake.integrations.notion.models import NotionClassification

_SOURCE_MAP = {
    ("telegram", "text"): "Telegram Text",
    ("telegram", "voice"): "Telegram Voice",
    ("telegram", "forwarded"): "Telegram Forward",
    ("telegram", "url"): "URL",
}


def channel_to_source(channel: str, message_type: str) -> str:
    return _SOURCE_MAP.get((channel, message_type), "Other")


def _rich_text(content: str) -> list[dict]:
    """Chunk content into Notion rich_text elements (max 2000 chars each)."""
    if not content:
        return [{"type": "text", "text": {"content": ""}}]
    chunks = []
    while content:
        chunks.append({"type": "text", "text": {"content": content[:2000]}})
        content = content[2000:]
    return chunks


def build_properties(
    classification: NotionClassification,
    captured_at: datetime,
    source: str,
) -> dict:
    props: dict = {
        "Name": {"title": [{"text": {"content": classification.title[:2000]}}]},
        "Project": {"select": {"name": classification.project}},
        "Content Type": {"select": {"name": classification.content_type}},
        "Status": {"select": {"name": classification.notion_status}},
        "Source": {"select": {"name": source}},
        "Capture Context": {"select": {"name": classification.capture_context}},
        "Captured At": {"date": {"start": captured_at.isoformat()}},
        "Summary": {"rich_text": _rich_text(classification.summary[:2000])},
        "Actionable": {"checkbox": classification.actionable},
        "Next Action": {"rich_text": _rich_text((classification.next_action or "")[:2000])},
        "Tags": {
            "multi_select": [{"name": t[:100]} for t in classification.tags[:10]]
        },
        "Confidence": {"number": round(classification.confidence, 4)},
        "D.R.A.K.E. Task ID": {
            "rich_text": [{"type": "text", "text": {"content": classification.task_id[:2000]}}]
        },
        "D.R.A.K.E. Artifact ID": {
            "rich_text": [
                {"type": "text", "text": {"content": (classification.artifact_id or "")[:2000]}}
            ]
        },
        "Sync Status": {"select": {"name": "Synced"}},
    }
    if classification.source_url:
        props["Source URL"] = {"url": classification.source_url}
    return props
