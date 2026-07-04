from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from operation_drake.integrations.notion.body_builder import build_body
from operation_drake.integrations.notion.client import NotionClientInterface
from operation_drake.integrations.notion.errors import (
    NotionAPIError,
    NotionAuthError,
    NotionRateLimitError,
    NotionTimeoutError,
)
from operation_drake.integrations.notion.mapper import build_properties, channel_to_source
from operation_drake.integrations.notion.models import NotionClassification, SyncResult
from operation_drake.models.schemas import NotionSyncCreate
from operation_drake.observability.logging import get_logger
from operation_drake.storage.repositories import NotionSyncRepository

logger = get_logger(__name__)


class NotionSyncService:
    def __init__(
        self,
        session: Session,
        client: NotionClientInterface,
        database_id: str,
        low_confidence_threshold: float = 0.70,
    ) -> None:
        self._repo = NotionSyncRepository(session)
        self._client = client
        self._database_id = database_id
        self._threshold = low_confidence_threshold

    def sync(
        self,
        task_id: str,
        artifact_id: str | None,
        classification: NotionClassification,
        captured_at: datetime,
        channel: str = "telegram",
        message_type: str = "text",
    ) -> SyncResult:
        if not classification.sync_to_notion:
            logger.info({"action": "notion_sync_skipped", "task_id": task_id, "reason": "user_opt_out"})
            return SyncResult(status="skipped")

        idempotency_key = f"notion:{task_id}"
        existing_record = self._repo.get_by_idempotency_key(idempotency_key)

        if (
            existing_record
            and existing_record.sync_status == "synced"
            and existing_record.external_page_id
        ):
            logger.info({"action": "notion_already_synced", "task_id": task_id})
            url = f"https://notion.so/{existing_record.external_page_id.replace('-', '')}"
            return SyncResult(
                status="already_synced",
                page_id=existing_record.external_page_id,
                page_url=url,
                needs_review=(classification.notion_status == "Needs Review"),
            )

        if not existing_record:
            existing_record = self._repo.create(
                NotionSyncCreate(
                    idempotency_key=idempotency_key,
                    task_id=task_id,
                    artifact_id=artifact_id,
                )
            )

        self._repo.record_attempt(existing_record.id)

        source = channel_to_source(channel, message_type)
        properties = build_properties(classification, captured_at, source)
        children = build_body(classification)

        try:
            existing_page = self._client.find_page_by_task_id(task_id)

            if existing_page:
                page_id, page_url = self._client.update_page(existing_page["id"], properties)
                self._repo.mark_synced(existing_record.id, page_id)
                logger.info({"action": "notion_page_updated", "task_id": task_id, "page_id": page_id})
                return SyncResult(
                    status="updated",
                    page_id=page_id,
                    page_url=page_url,
                    needs_review=(classification.notion_status == "Needs Review"),
                )
            else:
                page_id, page_url = self._client.create_page(properties, children)
                self._repo.mark_synced(existing_record.id, page_id)
                logger.info({"action": "notion_page_created", "task_id": task_id, "page_id": page_id})
                return SyncResult(
                    status="synced",
                    page_id=page_id,
                    page_url=page_url,
                    needs_review=(classification.notion_status == "Needs Review"),
                )

        except NotionAuthError:
            self._repo.mark_failed(existing_record.id, "auth")
            logger.error({"action": "notion_sync_failed", "task_id": task_id, "category": "auth"})
            return SyncResult(status="failed", error_category="auth")
        except NotionRateLimitError:
            self._repo.mark_failed(existing_record.id, "rate_limit")
            logger.warning({"action": "notion_sync_failed", "task_id": task_id, "category": "rate_limit"})
            return SyncResult(status="failed", error_category="rate_limit")
        except NotionTimeoutError:
            self._repo.mark_failed(existing_record.id, "timeout")
            logger.warning({"action": "notion_sync_failed", "task_id": task_id, "category": "timeout"})
            return SyncResult(status="failed", error_category="timeout")
        except NotionAPIError:
            self._repo.mark_failed(existing_record.id, "api_error")
            logger.error({"action": "notion_sync_failed", "task_id": task_id, "category": "api_error"})
            return SyncResult(status="failed", error_category="api_error")
        except Exception:
            self._repo.mark_failed(existing_record.id, "unknown")
            logger.error({"action": "notion_sync_failed", "task_id": task_id, "category": "unknown"})
            return SyncResult(status="failed", error_category="unknown")

    def sync_by_task_id(self, task_id: str) -> SyncResult:
        record = self._repo.get_by_task_id(task_id)
        if not record:
            return SyncResult(status="not_found")
        if record.sync_status == "synced" and record.external_page_id:
            url = f"https://notion.so/{record.external_page_id.replace('-', '')}"
            return SyncResult(
                status="already_synced",
                page_id=record.external_page_id,
                page_url=url,
            )
        classification = NotionClassification(task_id=task_id)
        return self.sync(
            task_id=task_id,
            artifact_id=record.artifact_id,
            classification=classification,
            captured_at=record.created_at or datetime.now(UTC),
        )

    def sync_pending(self, limit: int = 20) -> list[SyncResult]:
        records = self._repo.list_pending(limit=limit)
        results = []
        for record in records:
            classification = NotionClassification(task_id=record.task_id)
            result = self.sync(
                task_id=record.task_id,
                artifact_id=record.artifact_id,
                classification=classification,
                captured_at=record.created_at or datetime.now(UTC),
            )
            results.append(result)
        return results

    def get_status(self) -> dict:
        last_synced = self._repo.get_last_synced_at()
        return {
            "pending": self._repo.count_pending(),
            "failed": self._repo.count_failed(),
            "last_synced_at": last_synced.isoformat() if last_synced else None,
        }
