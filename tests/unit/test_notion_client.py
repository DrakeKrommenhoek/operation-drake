import pytest

from operation_drake.integrations.notion.errors import (
    NotionAPIError,
    NotionAuthError,
    NotionRateLimitError,
    NotionTimeoutError,
)
from operation_drake.integrations.notion.mock_client import MockNotionClient
from operation_drake.integrations.notion.models import NotionClassification, SyncResult


def test_mock_client_create_page_success():
    client = MockNotionClient()
    page_id, url = client.create_page({"Name": {"title": []}}, [])
    assert page_id
    assert "notion.so" in url
    assert len(client.created_pages) == 1


def test_mock_client_update_page_success():
    client = MockNotionClient()
    page_id, url = client.update_page("existing-id", {})
    assert page_id == "existing-id"
    assert len(client.updated_pages) == 1


def test_mock_client_find_page_returns_none_when_not_set():
    client = MockNotionClient()
    assert client.find_page_by_task_id("task-1") is None


def test_mock_client_find_page_returns_dict_when_set():
    client = MockNotionClient(existing_page_id="page-xyz")
    result = client.find_page_by_task_id("task-1")
    assert result["id"] == "page-xyz"


def test_mock_client_fails_with_auth():
    client = MockNotionClient(should_fail=True, fail_with="auth")
    with pytest.raises(NotionAuthError):
        client.create_page({}, [])


def test_mock_client_fails_with_rate_limit():
    client = MockNotionClient(should_fail=True, fail_with="rate_limit")
    with pytest.raises(NotionRateLimitError):
        client.create_page({}, [])


def test_mock_client_fails_with_timeout():
    client = MockNotionClient(should_fail=True, fail_with="timeout")
    with pytest.raises(NotionTimeoutError):
        client.create_page({}, [])


def test_mock_client_fails_with_unknown():
    client = MockNotionClient(should_fail=True, fail_with="unknown")
    with pytest.raises(NotionAPIError):
        client.create_page({}, [])


def test_notion_classification_defaults():
    c = NotionClassification(title="test")
    assert c.project == "General"
    assert c.content_type == "General Note"
    assert c.sync_to_notion is True
    assert c.notion_status == "Inbox"
    assert c.tags == []
    assert c.actionable is False


def test_sync_result_fields():
    r = SyncResult(status="synced", page_id="abc", page_url="https://notion.so/abc")
    assert r.status == "synced"
    assert r.needs_review is False


def test_mock_client_get_database_properties():
    client = MockNotionClient()
    assert client.get_database_properties() == {}
