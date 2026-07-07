from __future__ import annotations

import uuid

from operation_drake.integrations.notion.client import NotionClientInterface
from operation_drake.integrations.notion.errors import (
    NotionAPIError,
    NotionAuthError,
    NotionRateLimitError,
    NotionTimeoutError,
)


class MockNotionClient(NotionClientInterface):
    def __init__(
        self,
        should_fail: bool = False,
        fail_with: str = "unknown",
        existing_page_id: str | None = None,
        stale_pages: list[dict] | None = None,
    ) -> None:
        self._should_fail = should_fail
        self._fail_with = fail_with
        self._existing_page_id = existing_page_id
        self._stale_pages = stale_pages or []
        self.created_pages: list[dict] = []
        self.updated_pages: list[dict] = []

    def _maybe_fail(self) -> None:
        if not self._should_fail:
            return
        if self._fail_with == "auth":
            raise NotionAuthError("Mock auth failure")
        if self._fail_with == "rate_limit":
            raise NotionRateLimitError("Mock rate limit")
        if self._fail_with == "timeout":
            raise NotionTimeoutError("Mock timeout")
        raise NotionAPIError("Mock API error")

    def create_page(self, properties: dict, children: list[dict]) -> tuple[str, str]:
        self._maybe_fail()
        page_id = str(uuid.uuid4())
        self.created_pages.append({"id": page_id, "properties": properties})
        return page_id, f"https://notion.so/{page_id.replace('-', '')}"

    def update_page(self, page_id: str, properties: dict) -> tuple[str, str]:
        self._maybe_fail()
        self.updated_pages.append({"id": page_id, "properties": properties})
        return page_id, f"https://notion.so/{page_id.replace('-', '')}"

    def find_page_by_task_id(self, task_id: str) -> dict | None:
        if self._existing_page_id:
            return {"id": self._existing_page_id}
        return None

    def get_database_properties(self) -> dict:
        return {}

    def query_stale_by_content_type(self, content_type: str, older_than_iso: str) -> list[dict]:
        self._maybe_fail()
        return list(self._stale_pages)
