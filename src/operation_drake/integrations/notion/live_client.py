from __future__ import annotations

import httpx

from operation_drake.integrations.notion.client import NotionClientInterface
from operation_drake.integrations.notion.errors import (
    NotionAPIError,
    NotionAuthError,
    NotionNotFoundError,
    NotionRateLimitError,
    NotionTimeoutError,
)
from operation_drake.observability.logging import get_logger

logger = get_logger(__name__)

_API_BASE = "https://api.notion.com/v1"
# Pin to the stable API version to avoid SDK version mismatches.
# The Python SDK defaults change with each release; using the stable
# 2022-06-28 version ensures consistent schema/query behaviour.
_NOTION_VERSION = "2022-06-28"


class LiveNotionClient(NotionClientInterface):
    def __init__(self, api_token: str, database_id: str) -> None:
        self._token = api_token
        self._database_id = database_id

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        json: dict | None = None,
        timeout: float = 30.0,
    ) -> dict:
        url = f"{_API_BASE}/{path.lstrip('/')}"
        try:
            resp = httpx.request(
                method=method,
                url=url,
                headers=self._headers(),
                json=json,
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            raise NotionTimeoutError("Request timed out") from exc
        except Exception as exc:
            raise NotionAPIError(f"Network error: {type(exc).__name__}") from exc
        return self._handle(resp)

    def _handle(self, resp: httpx.Response) -> dict:
        if resp.status_code == 200:
            return resp.json()
        # Log only the status code — never log full response (may contain auth context)
        logger.warning({"action": "notion_api_error", "status": resp.status_code})
        if resp.status_code == 401:
            raise NotionAuthError("Authentication failed")
        if resp.status_code == 429:
            raise NotionRateLimitError("Rate limited")
        if resp.status_code == 404:
            raise NotionNotFoundError("Resource not found")
        raise NotionAPIError(f"API error {resp.status_code}")

    # ------------------------------------------------------------------

    def create_page(self, properties: dict, children: list[dict]) -> tuple[str, str]:
        page = self._request(
            "POST",
            "/pages",
            json={
                "parent": {"database_id": self._database_id},
                "properties": properties,
                "children": children,
            },
        )
        page_id = page["id"]
        page_url = page.get("url", f"https://notion.so/{page_id.replace('-', '')}")
        return page_id, page_url

    def update_page(self, page_id: str, properties: dict) -> tuple[str, str]:
        page = self._request(
            "PATCH",
            f"/pages/{page_id}",
            json={"properties": properties},
        )
        page_url = page.get("url", f"https://notion.so/{page_id.replace('-', '')}")
        return page_id, page_url

    def find_page_by_task_id(self, task_id: str) -> dict | None:
        result = self._request(
            "POST",
            f"/databases/{self._database_id}/query",
            json={
                "filter": {
                    "property": "D.R.A.K.E. Task ID",
                    "rich_text": {"equals": task_id},
                },
                "page_size": 1,
            },
        )
        results = result.get("results", [])
        return results[0] if results else None

    def get_database_properties(self) -> dict:
        db = self._request("GET", f"/databases/{self._database_id}")
        return db.get("properties", {})

    def query_stale_by_content_type(self, content_type: str, older_than_iso: str) -> list[dict]:
        result = self._request(
            "POST",
            f"/databases/{self._database_id}/query",
            json={
                "filter": {
                    "and": [
                        {"property": "Content Type", "select": {"equals": content_type}},
                        {"property": "Captured At", "date": {"before": older_than_iso}},
                        {"property": "Status", "select": {"does_not_equal": "Archived"}},
                    ]
                },
                "page_size": 100,
            },
        )
        return result.get("results", [])
