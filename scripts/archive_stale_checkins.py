"""
Daily cron: archive Workday Check-in entries idle in Notion for 7+ days.
Run from the project root: python scripts/archive_stale_checkins.py
"""

from datetime import UTC, datetime, timedelta

from operation_drake.config import get_settings
from operation_drake.integrations.notion import get_notion_client
from operation_drake.observability.logging import get_logger

logger = get_logger(__name__)

STALE_DAYS = 7
CONTENT_TYPE = "Workday Check-in"


def main() -> int:
    settings = get_settings()
    if not settings.notion_enabled:
        print("Notion is not enabled; nothing to archive.")
        return 0

    client = get_notion_client(settings)
    cutoff = (datetime.now(UTC) - timedelta(days=STALE_DAYS)).date().isoformat()
    stale_pages = client.query_stale_by_content_type(CONTENT_TYPE, cutoff)

    if not stale_pages:
        print("No stale Workday Check-ins found.")
        return 0

    archived = 0
    for page in stale_pages:
        page_id = page.get("id")
        try:
            client.update_page(page_id, {"Status": {"select": {"name": "Archived"}}})
            archived += 1
        except Exception as e:
            logger.error(
                {
                    "action": "archive_stale_checkin_failed",
                    "page_id": page_id,
                    "error": str(e)[:100],
                }
            )

    print(f"Archived {archived}/{len(stale_pages)} stale Workday Check-ins.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
