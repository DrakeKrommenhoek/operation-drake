from __future__ import annotations

from dataclasses import dataclass

from operation_drake.integrations.notion.models import VALID_PROJECTS, match_project
from operation_drake.integrations.notion.sync_service import NotionSyncService


@dataclass
class WriteBackResult:
    ok: bool
    message: str


class WriteBackService:
    """Applies Telegram write-back commands (/done, /archive, /action,
    /project) to the Notion page for an already-captured task."""

    def __init__(self, notion_sync_service: NotionSyncService | None):
        self._notion_svc = notion_sync_service

    def _apply(self, task_id: str, properties: dict, confirm: str) -> WriteBackResult:
        if not self._notion_svc:
            return WriteBackResult(ok=False, message="Notion is not enabled.")
        result = self._notion_svc.update_properties(task_id, properties)
        if result.status == "not_found":
            return WriteBackResult(ok=False, message="No synced Notion page found for that task.")
        if result.status == "failed":
            return WriteBackResult(
                ok=False, message=f"Notion update failed ({result.error_category or 'unknown'})."
            )
        return WriteBackResult(ok=True, message=confirm)

    def mark_done(self, task_id: str) -> WriteBackResult:
        return self._apply(
            task_id, {"Status": {"select": {"name": "Organized"}}}, "Marked Organized."
        )

    def mark_archived(self, task_id: str) -> WriteBackResult:
        return self._apply(task_id, {"Status": {"select": {"name": "Archived"}}}, "Archived.")

    def mark_action_required(self, task_id: str) -> WriteBackResult:
        return self._apply(
            task_id,
            {
                "Status": {"select": {"name": "Action Required"}},
                "Actionable": {"checkbox": True},
            },
            "Marked Action Required.",
        )

    def set_project(self, task_id: str, query: str) -> WriteBackResult:
        matched = match_project(query)
        if not matched:
            options = ", ".join(sorted(VALID_PROJECTS))
            return WriteBackResult(
                ok=False, message=f"No project matched '{query}'. Options: {options}"
            )
        return self._apply(
            task_id, {"Project": {"select": {"name": matched}}}, f"Project set to {matched}."
        )
