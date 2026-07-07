from abc import ABC, abstractmethod


class NotionClientInterface(ABC):
    @abstractmethod
    def create_page(self, properties: dict, children: list[dict]) -> tuple[str, str]:
        """Create a page in the database. Returns (page_id, page_url)."""

    @abstractmethod
    def update_page(self, page_id: str, properties: dict) -> tuple[str, str]:
        """Update an existing page. Returns (page_id, page_url)."""

    @abstractmethod
    def find_page_by_task_id(self, task_id: str) -> dict | None:
        """Find an existing page by D.R.A.K.E. Task ID. Returns page dict or None."""

    @abstractmethod
    def get_database_properties(self) -> dict:
        """Return the database properties schema dict."""

    @abstractmethod
    def query_stale_by_content_type(self, content_type: str, older_than_iso: str) -> list[dict]:
        """Return page dicts with the given Content Type captured before
        older_than_iso (ISO date), excluding pages already Archived."""
