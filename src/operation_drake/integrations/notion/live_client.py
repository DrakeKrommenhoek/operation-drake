from __future__ import annotations

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


class LiveNotionClient(NotionClientInterface):
    def __init__(self, api_token: str, database_id: str) -> None:
        from notion_client import Client

        self._client = Client(auth=api_token)
        self._database_id = database_id

    def create_page(self, properties: dict, children: list[dict]) -> tuple[str, str]:
        try:
            page = self._client.pages.create(
                parent={"database_id": self._database_id},
                properties=properties,
                children=children,
            )
            page_id = page["id"]
            page_url = page.get("url", f"https://notion.so/{page_id.replace('-', '')}")
            return page_id, page_url
        except Exception as e:
            raise self._wrap(e) from e

    def update_page(self, page_id: str, properties: dict) -> tuple[str, str]:
        try:
            page = self._client.pages.update(page_id=page_id, properties=properties)
            page_url = page.get("url", f"https://notion.so/{page_id.replace('-', '')}")
            return page_id, page_url
        except Exception as e:
            raise self._wrap(e) from e

    def find_page_by_task_id(self, task_id: str) -> dict | None:
        try:
            result = self._client.databases.query(
                database_id=self._database_id,
                filter={
                    "property": "D.R.A.K.E. Task ID",
                    "rich_text": {"equals": task_id},
                },
            )
            results = result.get("results", [])
            return results[0] if results else None
        except Exception as e:
            raise self._wrap(e) from e

    def get_database_properties(self) -> dict:
        try:
            db = self._client.databases.retrieve(database_id=self._database_id)
            return db.get("properties", {})
        except Exception as e:
            raise self._wrap(e) from e

    def _wrap(self, exc: Exception) -> NotionAPIError:
        try:
            from notion_client.errors import APIResponseError

            if isinstance(exc, APIResponseError):
                status = getattr(exc, "status", 0)
                # Log only the status code — never log full error payload (may contain auth headers)
                logger.warning({"action": "notion_api_error", "status": status})
                if status == 401:
                    return NotionAuthError("Authentication failed")
                if status == 429:
                    return NotionRateLimitError("Rate limited")
                if status == 404:
                    return NotionNotFoundError("Resource not found")
                return NotionAPIError(f"API error {status}")
        except ImportError:
            pass

        msg = str(exc)
        if "timeout" in msg.lower() or "timed out" in msg.lower():
            return NotionTimeoutError("Request timed out")
        logger.error({"action": "notion_unexpected_error", "type": type(exc).__name__})
        return NotionAPIError("Unexpected error")
