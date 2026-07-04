from __future__ import annotations

from operation_drake.config import Settings
from operation_drake.observability.logging import get_logger

logger = get_logger(__name__)

_REQUIRED_PROPERTIES = [
    "Name",
    "Project",
    "Content Type",
    "Status",
    "Source",
    "Capture Context",
    "Captured At",
    "Summary",
    "Actionable",
    "Next Action",
    "Tags",
    "Confidence",
    "Source URL",
    "D.R.A.K.E. Task ID",
    "D.R.A.K.E. Artifact ID",
    "Sync Status",
]

_PROJECT_OPTIONS = [
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
]

_CONTENT_TYPE_OPTIONS = [
    "Idea",
    "Reflection",
    "Research",
    "Resource",
    "Action Plan",
    "Meeting Note",
    "Decision",
    "Journal Entry",
    "Workday Check-in",
    "Article or Media Capture",
    "Voice Memo",
    "General Note",
]

_STATUS_OPTIONS = ["Inbox", "Organized", "Needs Review", "Action Required", "Archived"]

_SOURCE_OPTIONS = [
    "Telegram Text",
    "Telegram Voice",
    "Telegram Forward",
    "URL",
    "Article",
    "Video",
    "Social Post",
    "ChatGPT Voice",
    "Manual",
    "Other",
]

_CONTEXT_OPTIONS = [
    "General",
    "Pre-work Drive",
    "Post-work Drive",
    "Commute",
    "Work",
    "School",
    "Workout",
    "Evening Reflection",
    "Weekend Planning",
]

_SYNC_STATUS_OPTIONS = ["Synced", "Pending", "Failed", "Needs Review"]


def _database_properties_schema() -> dict:
    return {
        "Name": {"title": {}},
        "Project": {"select": {"options": [{"name": n} for n in _PROJECT_OPTIONS]}},
        "Content Type": {"select": {"options": [{"name": n} for n in _CONTENT_TYPE_OPTIONS]}},
        "Status": {"select": {"options": [{"name": n} for n in _STATUS_OPTIONS]}},
        "Source": {"select": {"options": [{"name": n} for n in _SOURCE_OPTIONS]}},
        "Capture Context": {"select": {"options": [{"name": n} for n in _CONTEXT_OPTIONS]}},
        "Captured At": {"date": {}},
        "Summary": {"rich_text": {}},
        "Actionable": {"checkbox": {}},
        "Next Action": {"rich_text": {}},
        "Tags": {"multi_select": {"options": []}},
        "Confidence": {"number": {"format": "number"}},
        "Source URL": {"url": {}},
        "D.R.A.K.E. Task ID": {"rich_text": {}},
        "D.R.A.K.E. Artifact ID": {"rich_text": {}},
        "Sync Status": {"select": {"options": [{"name": n} for n in _SYNC_STATUS_OPTIONS]}},
    }


def run_check_notion(settings: Settings) -> int:
    rows: list[tuple[str, str]] = []
    issues: list[str] = []

    rows.append(
        ("Notion enabled", "yes" if settings.notion_enabled else "no (NOTION_ENABLED=false)")
    )
    if not settings.notion_enabled:
        _print_table(rows)
        return 0

    token_ok = bool(settings.notion_api_token)
    rows.append(("API token", "present" if token_ok else "FAIL -- set NOTION_API_TOKEN"))
    if not token_ok:
        issues.append("NOTION_API_TOKEN not set")
        _print_table(rows, issues)
        return 1

    db_configured = bool(settings.notion_database_id)
    parent_configured = bool(settings.notion_parent_page_id)
    rows.append(("Database ID", "configured" if db_configured else "not set"))
    rows.append(("Parent page ID", "configured" if parent_configured else "not set"))

    if not db_configured and not parent_configured:
        issues.append("Set NOTION_DATABASE_ID or NOTION_PARENT_PAGE_ID")
        _print_table(rows, issues)
        return 1

    schema_needs_repair = False
    if db_configured:
        try:
            from operation_drake.integrations.notion.live_client import LiveNotionClient

            client = LiveNotionClient(settings.notion_api_token, settings.notion_database_id)
            props = client.get_database_properties()
            missing = [p for p in _REQUIRED_PROPERTIES if p not in props]
            if missing:
                rows.append(("Schema", f"WARN -- missing: {', '.join(missing[:5])}"))
                schema_needs_repair = True
            else:
                rows.append(("Schema", "compatible"))
            rows.append(("Connection", "OK"))
        except Exception as e:
            rows.append(("Connection", f"FAIL -- {type(e).__name__}"))
            issues.append("Could not connect to Notion database")

    _print_table(rows, issues)
    return (2 if schema_needs_repair else 0) if not issues else 1


def run_setup_notion(settings: Settings) -> int:
    if not settings.notion_enabled:
        print("Notion is disabled. Set NOTION_ENABLED=true in .env to proceed.")
        return 1
    if not settings.notion_api_token:
        print("NOTION_API_TOKEN is not set in .env")
        return 1

    if settings.notion_database_id:
        # Database ID is set — check schema and repair if needed
        print("NOTION_DATABASE_ID is already set. Checking schema...")
        check_result = run_check_notion(settings)
        if check_result == 0:
            print("Schema is already complete.")
            return 0
        if check_result == 1:
            print("Connection failed — cannot apply schema.")
            return 1
        # check_result == 2: schema is missing properties
        print("Applying missing properties to existing database...")
        return _apply_schema_to_existing(settings)

    if not settings.notion_parent_page_id:
        print("Set NOTION_PARENT_PAGE_ID to a Notion page you have shared with your integration.")
        print("Then re-run: python -m operation_drake.main --setup-notion")
        return 1

    print("Checking for existing D.R.A.K.E. Knowledge Vault database...")
    try:
        from notion_client import Client

        client = Client(auth=settings.notion_api_token)

        # Search without type filter (Notion API no longer accepts "database" as filter value)
        search = client.search(query="D.R.A.K.E. Knowledge Vault")
        parent_id_clean = settings.notion_parent_page_id.replace("-", "")
        for result in search.get("results", []):
            if result.get("object") != "database":
                continue
            parent = result.get("parent", {})
            if parent.get("page_id", "").replace("-", "") == parent_id_clean:
                db_id = result["id"]
                print("Found existing database.")
                print("Add to .env:")
                print(f"NOTION_DATABASE_ID={db_id}")
                return 0

        print("Creating D.R.A.K.E. Knowledge Vault database...")
        db = client.databases.create(
            parent={"type": "page_id", "page_id": settings.notion_parent_page_id},
            title=[{"type": "text", "text": {"content": "D.R.A.K.E. Knowledge Vault"}}],
            properties=_database_properties_schema(),
        )
        db_id = db["id"]
        print("Database created successfully.")
        print("Add the following to your .env file:")
        print(f"NOTION_DATABASE_ID={db_id}")
        return 0
    except Exception as e:
        print(f"Setup failed: {type(e).__name__}")
        logger.error({"action": "notion_setup_failed", "type": type(e).__name__})
        return 1


def _apply_schema_to_existing(settings: Settings) -> int:
    """Apply properties schema to an existing database using the stable Notion API version."""
    try:
        import httpx

        headers = {
            "Authorization": f"Bearer {settings.notion_api_token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        props = _database_properties_schema()
        resp = httpx.patch(
            f"https://api.notion.com/v1/databases/{settings.notion_database_id}",
            headers=headers,
            json={"properties": props},
            timeout=30,
        )
        if resp.status_code == 200:
            applied = resp.json().get("properties", {})
            print(f"Schema applied: {len(applied)} properties set.")
            return 0
        print(f"Schema apply failed: HTTP {resp.status_code}")
        logger.error({"action": "notion_schema_apply_failed", "status": resp.status_code})
        return 1
    except Exception as e:
        print(f"Schema apply failed: {type(e).__name__}")
        logger.error({"action": "notion_schema_apply_failed", "type": type(e).__name__})
        return 1


def _print_table(rows: list[tuple[str, str]], issues: list[str] | None = None) -> None:
    col_width = max(len(r[0]) for r in rows) + 2
    width = col_width + 40
    print("\n  D.R.A.K.E. -- Notion Check")
    print("-" * width)
    for label, value in rows:
        print(f"  {label:<{col_width}}{value}")
    print("-" * width)
    if issues:
        print(f"\n  FAIL: {len(issues)} issue(s):")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print("\n  All checks passed.\n")
