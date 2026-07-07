from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

from operation_drake.integrations.notion.mock_client import MockNotionClient

_SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "archive_stale_checkins.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("archive_stale_checkins", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mock_client_query_stale_returns_configured_pages():
    pages = [{"id": "page-1"}, {"id": "page-2"}]
    client = MockNotionClient(stale_pages=pages)
    result = client.query_stale_by_content_type("Workday Check-in", "2026-06-01")
    assert result == pages


def test_mock_client_query_stale_empty_by_default():
    client = MockNotionClient()
    assert client.query_stale_by_content_type("Workday Check-in", "2026-06-01") == []


def test_archive_script_skips_when_notion_disabled(capsys):
    module = _load_script()
    settings = MagicMock(notion_enabled=False)
    module.get_settings = lambda: settings
    exit_code = module.main()
    assert exit_code == 0
    assert "not enabled" in capsys.readouterr().out.lower()


def test_archive_script_archives_all_stale_pages(capsys):
    module = _load_script()
    settings = MagicMock(notion_enabled=True)
    client = MockNotionClient(stale_pages=[{"id": "p1"}, {"id": "p2"}, {"id": "p3"}])
    module.get_settings = lambda: settings
    module.get_notion_client = lambda s: client
    exit_code = module.main()
    assert exit_code == 0
    assert len(client.updated_pages) == 3
    for update in client.updated_pages:
        assert update["properties"]["Status"]["select"]["name"] == "Archived"
    assert "Archived 3/3" in capsys.readouterr().out


def test_archive_script_reports_no_stale_entries(capsys):
    module = _load_script()
    settings = MagicMock(notion_enabled=True)
    client = MockNotionClient(stale_pages=[])
    module.get_settings = lambda: settings
    module.get_notion_client = lambda s: client
    exit_code = module.main()
    assert exit_code == 0
    assert "no stale" in capsys.readouterr().out.lower()


def test_archive_script_continues_after_one_failure(capsys):
    module = _load_script()
    settings = MagicMock(notion_enabled=True)
    client = MockNotionClient(stale_pages=[{"id": "p1"}, {"id": "p2"}])

    calls = {"n": 0}
    original_update = client.update_page

    def flaky_update(page_id, properties):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return original_update(page_id, properties)

    client.update_page = flaky_update
    module.get_settings = lambda: settings
    module.get_notion_client = lambda s: client
    exit_code = module.main()
    assert exit_code == 0
    assert "Archived 1/2" in capsys.readouterr().out
