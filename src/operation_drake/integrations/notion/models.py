from __future__ import annotations

import difflib
from dataclasses import dataclass, field

VALID_PROJECTS: frozenset[str] = frozenset(
    {
        "General",
        "Business Ideas",
        "The Answer Movement",
        "Ascend",
        "Operation D.R.A.K.E.",
        "DK Personal Health OS",
        "Career & Work",
        "School & Learning",
        "Health & Fitness",
        "Investing & Finance",
        "Relationships & Networking",
        "Personal Life",
    }
)


def match_project(query: str) -> str | None:
    """Fuzzy-match free text against the 12 valid Notion Project values."""
    q = query.strip().lower()
    if not q:
        return None
    for project in VALID_PROJECTS:
        if project.lower() == q:
            return project
    for project in VALID_PROJECTS:
        if q in project.lower() or project.lower() in q:
            return project
    lowered = {p.lower(): p for p in VALID_PROJECTS}
    close = difflib.get_close_matches(q, lowered.keys(), n=1, cutoff=0.6)
    return lowered[close[0]] if close else None


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
