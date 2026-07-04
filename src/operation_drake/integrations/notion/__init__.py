from __future__ import annotations

from operation_drake.integrations.notion.client import NotionClientInterface
from operation_drake.integrations.notion.mock_client import MockNotionClient


def get_notion_client(settings) -> NotionClientInterface:
    """Return live client when Notion is enabled and configured, otherwise no-op mock."""
    if not settings.notion_enabled or not settings.notion_api_token:
        return MockNotionClient()
    from operation_drake.integrations.notion.live_client import LiveNotionClient

    return LiveNotionClient(
        api_token=settings.notion_api_token,
        database_id=settings.notion_database_id,
    )
