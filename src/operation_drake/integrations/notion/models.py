from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NotionClassification:
    project: str = "General"
    content_type: str = "General Note"
    title: str = ""
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    actionable: bool = False
    next_action: str = ""
    capture_context: str = "General"
    confidence: float = 0.5
    sync_to_notion: bool = True
    notion_status: str = "Inbox"
    task_id: str = ""
    artifact_id: str | None = None
    source_url: str | None = None


@dataclass
class SyncResult:
    status: str  # synced, updated, already_synced, failed, skipped, disabled, not_found
    page_id: str | None = None
    page_url: str | None = None
    error_category: str | None = None
    needs_review: bool = False
