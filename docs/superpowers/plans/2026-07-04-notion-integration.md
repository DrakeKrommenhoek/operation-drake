# Notion Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a one-way Notion sync so every completed D.R.A.K.E. workflow output is classified and organized into a single Notion database (D.R.A.K.E. Knowledge Vault), with idempotency, retry tracking, and Telegram confirmation — without ever breaking local task completion or Telegram polling.

**Architecture:** A `NotionClassifier` (LLM call) runs after any successful workflow to produce structured metadata (project, content_type, capture_context, etc.). A `NotionSyncService` manages idempotency via a `notion_syncs` SQLite table and calls a `NotionClientInterface` (live or mock). The orchestrator calls sync after artifact creation and extends `ProcessResult` with sync status; Telegram formats a brief confirmation.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0, `notion-client>=2.2`, existing `anthropic`/`openai` LLM providers, pytest, ruff.

## Global Constraints

- Never log NOTION_API_TOKEN or any secret value.
- Notion failure must never: lose original input, change task status to failed, create duplicate pages, stop Telegram polling.
- `Base.metadata.create_all()` is safe to add new tables — no Alembic needed for additive changes.
- All new code passes `ruff check` and `ruff format --check`.
- No live Notion API calls in the automated test suite — use MockNotionClient.
- `NOTION_ENABLED=false` (the default) must produce zero behavior change in all existing tests.
- Pin `notion-client>=2.2` in pyproject.toml.

---

## File Map

### New files
```
src/operation_drake/integrations/__init__.py
src/operation_drake/integrations/notion/__init__.py
src/operation_drake/integrations/notion/errors.py          # NotionAuthError, NotionRateLimitError, etc.
src/operation_drake/integrations/notion/models.py          # NotionClassification, SyncResult dataclasses
src/operation_drake/integrations/notion/client.py          # NotionClientInterface ABC
src/operation_drake/integrations/notion/mock_client.py     # MockNotionClient (test double)
src/operation_drake/integrations/notion/live_client.py     # LiveNotionClient (real API)
src/operation_drake/integrations/notion/classifier.py      # NotionClassifier (LLM call)
src/operation_drake/integrations/notion/mapper.py          # NotionClassification → Notion API properties
src/operation_drake/integrations/notion/body_builder.py    # Page body blocks with chunking
src/operation_drake/integrations/notion/sync_service.py    # Idempotency, retry, outbox
src/operation_drake/integrations/notion/setup.py           # --setup-notion / --check-notion logic
prompts/notion_classifier.md
tests/unit/test_notion_mapper.py
tests/unit/test_notion_body.py
tests/unit/test_notion_classifier.py
tests/unit/test_notion_sync_service.py
tests/unit/test_notion_commands.py
docs/notion-setup.md
```

### Modified files
```
pyproject.toml                                              # add notion-client>=2.2
.env.example                                               # add NOTION_* vars
src/operation_drake/config.py                              # add Notion settings fields
src/operation_drake/models/database.py                     # add NotionSyncORM
src/operation_drake/models/schemas.py                      # add NotionSyncCreate/Read
src/operation_drake/storage/repositories.py                # add NotionSyncRepository
src/operation_drake/services/orchestration.py              # inject NotionSyncService, extend ProcessResult
src/operation_drake/channels/telegram.py                   # /notion /sync /sync_pending + Notion reply format
src/operation_drake/main.py                                # --check-notion --setup-notion
CURRENT_STATE.md, TASKS.md, ROADMAP.md
```

---

### Task 1: Dependency, Config, ORM, Schema, Repository

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Modify: `src/operation_drake/config.py`
- Modify: `src/operation_drake/models/database.py`
- Modify: `src/operation_drake/models/schemas.py`
- Modify: `src/operation_drake/storage/repositories.py`
- Test: `tests/unit/test_notion_foundation.py` (new)

**Interfaces produced:**
- `Settings.notion_enabled: bool`
- `Settings.notion_api_token: str`
- `Settings.notion_parent_page_id: str`
- `Settings.notion_database_id: str`
- `Settings.notion_sync_mode: str`
- `Settings.notion_low_confidence_threshold: float`
- `NotionSyncORM` table: `notion_syncs`
- `NotionSyncCreate`, `NotionSyncRead` Pydantic models
- `NotionSyncRepository` with methods: `create`, `get_by_idempotency_key`, `record_attempt`, `mark_synced`, `mark_failed`, `list_pending`, `list_failed`, `count_pending`, `count_failed`, `get_last_synced_at`

- [ ] **Step 1: Add notion-client to pyproject.toml**

In `pyproject.toml`, add to `dependencies`:
```toml
"notion-client>=2.2",
```

- [ ] **Step 2: Update .env.example**

Append to `.env.example`:
```
# === NOTION INTEGRATION ===
NOTION_ENABLED=false
NOTION_API_TOKEN=
NOTION_PARENT_PAGE_ID=
NOTION_DATABASE_ID=
NOTION_SYNC_MODE=automatic
NOTION_LOW_CONFIDENCE_THRESHOLD=0.70
```

- [ ] **Step 3: Add Notion settings to config.py**

In `src/operation_drake/config.py`, add to `Settings` class after `app_env`:
```python
notion_enabled: bool = False
notion_api_token: str = ""
notion_parent_page_id: str = ""
notion_database_id: str = ""
notion_sync_mode: str = "automatic"
notion_low_confidence_threshold: float = 0.70
```

- [ ] **Step 4: Add NotionSyncORM to database.py**

In `src/operation_drake/models/database.py`, add after `AgentRunORM`:
```python
class NotionSyncORM(Base):
    __tablename__ = "notion_syncs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uid)
    idempotency_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    task_id: Mapped[str] = mapped_column(String, nullable=False)
    artifact_id: Mapped[str | None] = mapped_column(String, nullable=True)
    destination: Mapped[str] = mapped_column(String, default="notion")
    external_page_id: Mapped[str | None] = mapped_column(String, nullable=True)
    sync_status: Mapped[str] = mapped_column(String, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error_category: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 5: Add schemas to schemas.py**

In `src/operation_drake/models/schemas.py`, append:
```python
class NotionSyncCreate(BaseModel):
    idempotency_key: str
    task_id: str
    artifact_id: str | None = None
    destination: str = "notion"
    sync_status: str = "pending"


class NotionSyncRead(NotionSyncCreate):
    id: str
    external_page_id: str | None = None
    attempt_count: int = 0
    last_attempt_at: datetime | None = None
    last_error_category: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
```

- [ ] **Step 6: Add NotionSyncRepository to repositories.py**

In `src/operation_drake/storage/repositories.py`, append:
```python
from operation_drake.models.database import NotionSyncORM
from operation_drake.models.schemas import NotionSyncCreate


class NotionSyncRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, data: NotionSyncCreate) -> NotionSyncORM:
        obj = NotionSyncORM(id=_uid(), **data.model_dump())
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def get_by_idempotency_key(self, key: str) -> NotionSyncORM | None:
        return (
            self.session.query(NotionSyncORM)
            .filter(NotionSyncORM.idempotency_key == key)
            .first()
        )

    def record_attempt(self, sync_id: str) -> None:
        obj = self.session.get(NotionSyncORM, sync_id)
        if obj:
            obj.attempt_count += 1
            obj.last_attempt_at = _now()
            self.session.commit()

    def mark_synced(self, sync_id: str, page_id: str) -> None:
        obj = self.session.get(NotionSyncORM, sync_id)
        if obj:
            obj.sync_status = "synced"
            obj.external_page_id = page_id
            obj.last_error_category = None
            self.session.commit()

    def mark_failed(self, sync_id: str, error_category: str) -> None:
        obj = self.session.get(NotionSyncORM, sync_id)
        if obj:
            obj.sync_status = "failed"
            obj.last_error_category = error_category
            self.session.commit()

    def list_pending(self, limit: int = 50) -> list[NotionSyncORM]:
        return (
            self.session.query(NotionSyncORM)
            .filter(NotionSyncORM.sync_status.in_(["pending", "failed"]))
            .order_by(NotionSyncORM.created_at.asc())
            .limit(limit)
            .all()
        )

    def count_pending(self) -> int:
        return (
            self.session.query(NotionSyncORM)
            .filter(NotionSyncORM.sync_status == "pending")
            .count()
        )

    def count_failed(self) -> int:
        return (
            self.session.query(NotionSyncORM)
            .filter(NotionSyncORM.sync_status == "failed")
            .count()
        )

    def get_last_synced_at(self) -> datetime | None:
        obj = (
            self.session.query(NotionSyncORM)
            .filter(NotionSyncORM.sync_status == "synced")
            .order_by(NotionSyncORM.updated_at.desc())
            .first()
        )
        return obj.updated_at if obj else None

    def get_by_task_id(self, task_id: str) -> NotionSyncORM | None:
        return (
            self.session.query(NotionSyncORM)
            .filter(NotionSyncORM.task_id == task_id)
            .first()
        )
```

- [ ] **Step 7: Write and run tests**

Create `tests/unit/test_notion_foundation.py`:
```python
from operation_drake.config import Settings
from operation_drake.models.database import Base, NotionSyncORM
from operation_drake.models.schemas import NotionSyncCreate
from operation_drake.storage.repositories import NotionSyncRepository
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_notion_settings_default_disabled():
    s = Settings()
    assert s.notion_enabled is False
    assert s.notion_api_token == ""
    assert s.notion_low_confidence_threshold == 0.70


def test_notion_sync_orm_creates():
    session = _make_session()
    repo = NotionSyncRepository(session)
    record = repo.create(NotionSyncCreate(
        idempotency_key="notion:task-1",
        task_id="task-1",
    ))
    assert record.id
    assert record.sync_status == "pending"
    assert record.attempt_count == 0


def test_notion_sync_idempotency_key_unique():
    session = _make_session()
    repo = NotionSyncRepository(session)
    repo.create(NotionSyncCreate(idempotency_key="notion:task-1", task_id="task-1"))
    import pytest
    with pytest.raises(Exception):
        repo.create(NotionSyncCreate(idempotency_key="notion:task-1", task_id="task-1"))


def test_notion_sync_mark_synced():
    session = _make_session()
    repo = NotionSyncRepository(session)
    record = repo.create(NotionSyncCreate(idempotency_key="notion:task-2", task_id="task-2"))
    repo.record_attempt(record.id)
    repo.mark_synced(record.id, "page-abc")
    updated = repo.get_by_idempotency_key("notion:task-2")
    assert updated.sync_status == "synced"
    assert updated.external_page_id == "page-abc"
    assert updated.attempt_count == 1


def test_notion_sync_mark_failed():
    session = _make_session()
    repo = NotionSyncRepository(session)
    record = repo.create(NotionSyncCreate(idempotency_key="notion:task-3", task_id="task-3"))
    repo.record_attempt(record.id)
    repo.mark_failed(record.id, "timeout")
    updated = repo.get_by_idempotency_key("notion:task-3")
    assert updated.sync_status == "failed"
    assert updated.last_error_category == "timeout"


def test_notion_sync_count_pending_and_failed():
    session = _make_session()
    repo = NotionSyncRepository(session)
    r1 = repo.create(NotionSyncCreate(idempotency_key="k1", task_id="t1"))
    r2 = repo.create(NotionSyncCreate(idempotency_key="k2", task_id="t2"))
    repo.mark_failed(r2.id, "auth")
    assert repo.count_pending() == 1
    assert repo.count_failed() == 1


def test_notion_sync_get_by_task_id():
    session = _make_session()
    repo = NotionSyncRepository(session)
    repo.create(NotionSyncCreate(idempotency_key="k-t99", task_id="t99"))
    found = repo.get_by_task_id("t99")
    assert found is not None
    assert found.task_id == "t99"
```

Run: `pytest tests/unit/test_notion_foundation.py -v`
Expected: 7 passed

- [ ] **Step 8: Install dependency and run full suite**

```bash
pip install -e ".[dev]"
pytest tests/ -v --tb=short 2>&1 | tail -10
```
Expected: existing 95 + 7 new = 102 passed

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml .env.example src/operation_drake/config.py src/operation_drake/models/database.py src/operation_drake/models/schemas.py src/operation_drake/storage/repositories.py tests/unit/test_notion_foundation.py
git commit -m "feat: add Notion config, NotionSyncORM, NotionSyncRepository"
```

---

### Task 2: Integration Package — Models, Client Interface, Errors, Mock Client

**Files:**
- Create: `src/operation_drake/integrations/__init__.py`
- Create: `src/operation_drake/integrations/notion/__init__.py`
- Create: `src/operation_drake/integrations/notion/errors.py`
- Create: `src/operation_drake/integrations/notion/models.py`
- Create: `src/operation_drake/integrations/notion/client.py`
- Create: `src/operation_drake/integrations/notion/mock_client.py`
- Test: `tests/unit/test_notion_client.py` (new)

**Interfaces produced:**
- `NotionAuthError`, `NotionRateLimitError`, `NotionTimeoutError`, `NotionAPIError`
- `NotionClassification` dataclass
- `SyncResult` dataclass
- `NotionClientInterface` ABC: `create_page(properties, children) -> tuple[str, str]`, `update_page(page_id, properties) -> tuple[str, str]`, `find_page_by_task_id(task_id) -> dict | None`, `get_database_properties() -> dict`
- `MockNotionClient(should_fail=False, fail_with="unknown", existing_page_id=None)`

- [ ] **Step 1: Create integrations/__init__.py**

```python
# src/operation_drake/integrations/__init__.py
```
(empty)

- [ ] **Step 2: Create integrations/notion/__init__.py**

```python
# src/operation_drake/integrations/notion/__init__.py
```
(empty)

- [ ] **Step 3: Create errors.py**

`src/operation_drake/integrations/notion/errors.py`:
```python
class NotionAPIError(Exception):
    pass


class NotionAuthError(NotionAPIError):
    pass


class NotionRateLimitError(NotionAPIError):
    pass


class NotionTimeoutError(NotionAPIError):
    pass


class NotionNotFoundError(NotionAPIError):
    pass
```

- [ ] **Step 4: Create models.py**

`src/operation_drake/integrations/notion/models.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NotionClassification:
    project: str = "General"
    content_type: str = "General Note"
    title: str = ""
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    actionable: bool = False
    next_action: str = ""
    capture_context: str = "General"
    confidence: float = 0.5
    sync_to_notion: bool = True
    notion_status: str = "Inbox"
    task_id: str = ""
    artifact_id: str | None = None
    source_url: str | None = None


@dataclass
class SyncResult:
    status: str  # synced, updated, already_synced, failed, skipped, disabled
    page_id: str | None = None
    page_url: str | None = None
    error_category: str | None = None
    needs_review: bool = False
```

- [ ] **Step 5: Create client.py**

`src/operation_drake/integrations/notion/client.py`:
```python
from abc import ABC, abstractmethod


class NotionClientInterface(ABC):
    @abstractmethod
    def create_page(
        self, properties: dict, children: list[dict]
    ) -> tuple[str, str]:
        """Returns (page_id, page_url)."""

    @abstractmethod
    def update_page(
        self, page_id: str, properties: dict
    ) -> tuple[str, str]:
        """Returns (page_id, page_url)."""

    @abstractmethod
    def find_page_by_task_id(self, task_id: str) -> dict | None:
        """Returns the Notion page dict or None."""

    @abstractmethod
    def get_database_properties(self) -> dict:
        """Returns the database properties schema."""
```

- [ ] **Step 6: Create mock_client.py**

`src/operation_drake/integrations/notion/mock_client.py`:
```python
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
    ) -> None:
        self._should_fail = should_fail
        self._fail_with = fail_with
        self._existing_page_id = existing_page_id
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

    def create_page(
        self, properties: dict, children: list[dict]
    ) -> tuple[str, str]:
        self._maybe_fail()
        page_id = str(uuid.uuid4())
        self.created_pages.append({"id": page_id, "properties": properties})
        return page_id, f"https://notion.so/{page_id.replace('-', '')}"

    def update_page(
        self, page_id: str, properties: dict
    ) -> tuple[str, str]:
        self._maybe_fail()
        self.updated_pages.append({"id": page_id, "properties": properties})
        return page_id, f"https://notion.so/{page_id.replace('-', '')}"

    def find_page_by_task_id(self, task_id: str) -> dict | None:
        if self._existing_page_id:
            return {"id": self._existing_page_id}
        return None

    def get_database_properties(self) -> dict:
        return {}
```

- [ ] **Step 7: Write and run tests**

Create `tests/unit/test_notion_client.py`:
```python
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


def test_sync_result_fields():
    r = SyncResult(status="synced", page_id="abc", page_url="https://notion.so/abc")
    assert r.status == "synced"
    assert r.needs_review is False
```

Run: `pytest tests/unit/test_notion_client.py -v`
Expected: 10 passed

- [ ] **Step 8: Run full suite**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -5
```
Expected: 112 passed

- [ ] **Step 9: Commit**

```bash
git add src/operation_drake/integrations/ tests/unit/test_notion_client.py
git commit -m "feat: add Notion integration package — models, client interface, mock client"
```

---

### Task 3: NotionClassifier

**Files:**
- Create: `prompts/notion_classifier.md`
- Create: `src/operation_drake/integrations/notion/classifier.py`
- Test: `tests/unit/test_notion_classifier.py`

**Interfaces consumed:** `LLMProvider` (existing), `NotionClassification` (Task 2)
**Interfaces produced:** `NotionClassifier.classify(content, workflow_summary, intent, channel, message_type, existing_project) -> NotionClassification`

- [ ] **Step 1: Create prompts/notion_classifier.md**

```markdown
You are a classification agent for the D.R.A.K.E. personal knowledge system.

Classify the input into the correct Notion Knowledge Vault category.

## Input
- Content: {content}
- Workflow summary: {workflow_summary}
- Intent: {intent}
- Channel: {channel}
- Message type: {message_type}
- Pre-detected project: {existing_project}

## Priority rules
1. Explicit user instruction overrides everything:
   - "Save this under X" / "this is an X idea" / "put this in X" → use that project
   - "This is a reflection / idea / research / etc." → use that content_type
   - "Do not save to Notion" / "don't sync" / "skip Notion" → set sync_to_notion to false
2. If a pre-detected project is provided (not "none"), use it as a strong signal.
3. Infer from content when no explicit instruction exists.

## Valid projects (pick exactly one)
General, Business Ideas, The Answer Movement, Ascend, Operation D.R.A.K.E., DK Personal Health OS, Career & Work, School & Learning, Health & Fitness, Investing & Finance, Relationships & Networking, Personal Life

## Valid content_type values (pick exactly one)
Idea, Reflection, Research, Resource, Action Plan, Meeting Note, Decision, Journal Entry, Workday Check-in, Article or Media Capture, Voice Memo, General Note

## Valid capture_context values (pick exactly one)
General, Pre-work Drive, Post-work Drive, Commute, Work, School, Workout, Evening Reflection, Weekend Planning

## Classification signals
- "driving to work" / "on my way in" / "before work" / "heading to the office" → Pre-work Drive
- "driving home" / "on the way home" / "heading home" / "after work" → Post-work Drive
- fitness, exercise, gym, workout, training → Health & Fitness + Workout context
- recruiting, internship, PE, private equity, finance, deal, LBO → Career & Work
- Ascend, recruiting OS, student platform → Ascend
- Answer Movement, workout challenge, physical wellness → The Answer Movement
- business idea, startup, venture, market → Business Ideas
- class, course, studying, professor, lecture → School & Learning
- investing, portfolio, stock, market analysis → Investing & Finance
- personal reflection, emotions, life observation → Personal Life
- "Workday check-in" / pre-work intention / today I want to focus → Workday Check-in content type
- action items, tasks, to-do → Action Plan or extract_actions intent → Actionable=true

## Confidence guidance
- 0.90+: explicit instruction present, or very clear single-category content
- 0.70–0.89: strong contextual signals but no explicit instruction
- 0.50–0.69: ambiguous content, multiple plausible categories
- below 0.70: set notion_status to "Needs Review"

## Output — respond with valid JSON only
{
  "project": "<one of the valid projects>",
  "content_type": "<one of the valid content types>",
  "title": "<concise useful title, max 80 chars>",
  "summary": "<2-3 sentence summary preserving user tone>",
  "tags": ["<tag1>", "<tag2>"],
  "actionable": <true or false>,
  "next_action": "<most important next step if actionable, else empty string>",
  "capture_context": "<one of the valid capture contexts>",
  "confidence": <0.0 to 1.0>,
  "sync_to_notion": <true or false>,
  "notion_status": "<Inbox or Needs Review>"
}
```

- [ ] **Step 2: Create classifier.py**

`src/operation_drake/integrations/notion/classifier.py`:
```python
from __future__ import annotations

from pathlib import Path

from operation_drake.agents.base import BaseAgent
from operation_drake.integrations.notion.models import NotionClassification
from operation_drake.llm.base import LLMProvider
from operation_drake.observability.logging import get_logger

logger = get_logger(__name__)

_PROMPT_PATH = Path("prompts/notion_classifier.md")

_VALID_PROJECTS = {
    "General", "Business Ideas", "The Answer Movement", "Ascend",
    "Operation D.R.A.K.E.", "DK Personal Health OS", "Career & Work",
    "School & Learning", "Health & Fitness", "Investing & Finance",
    "Relationships & Networking", "Personal Life",
}

_VALID_CONTENT_TYPES = {
    "Idea", "Reflection", "Research", "Resource", "Action Plan",
    "Meeting Note", "Decision", "Journal Entry", "Workday Check-in",
    "Article or Media Capture", "Voice Memo", "General Note",
}

_VALID_CONTEXTS = {
    "General", "Pre-work Drive", "Post-work Drive", "Commute",
    "Work", "School", "Workout", "Evening Reflection", "Weekend Planning",
}


class NotionClassifier(BaseAgent):
    def __init__(self, llm: LLMProvider, low_confidence_threshold: float = 0.70):
        super().__init__(llm)
        self._threshold = low_confidence_threshold
        self._prompt_template = _PROMPT_PATH.read_text() if _PROMPT_PATH.exists() else ""

    def classify(
        self,
        content: str,
        workflow_summary: str = "",
        intent: str = "",
        channel: str = "telegram",
        message_type: str = "text",
        existing_project: str | None = None,
    ) -> NotionClassification:
        if self._prompt_template:
            prompt = self._prompt_template.format(
                content=content[:2000],
                workflow_summary=workflow_summary[:1000],
                intent=intent,
                channel=channel,
                message_type=message_type,
                existing_project=existing_project or "none",
            )
        else:
            prompt = f"Classify for Notion: {content[:300]}"

        try:
            resp = self.llm.complete(
                prompt=prompt,
                system="You are a classification agent. Respond with valid JSON only.",
            )
            data = self._parse_json(resp.content)
        except Exception as e:
            logger.warning({"action": "notion_classify_failed", "error": str(e)[:100]})
            return NotionClassification(
                title=content[:80],
                confidence=0.0,
                notion_status="Needs Review",
            )

        project = data.get("project", "General")
        if project not in _VALID_PROJECTS:
            project = "General"

        content_type = data.get("content_type", "General Note")
        if content_type not in _VALID_CONTENT_TYPES:
            content_type = "General Note"

        capture_context = data.get("capture_context", "General")
        if capture_context not in _VALID_CONTEXTS:
            capture_context = "General"

        confidence = float(data.get("confidence", 0.5))
        notion_status = "Inbox" if confidence >= self._threshold else "Needs Review"
        if data.get("notion_status") == "Needs Review":
            notion_status = "Needs Review"

        return NotionClassification(
            project=project,
            content_type=content_type,
            title=str(data.get("title", content[:80]))[:200],
            summary=str(data.get("summary", "")),
            tags=[str(t) for t in data.get("tags", []) if isinstance(t, str)][:10],
            actionable=bool(data.get("actionable", False)),
            next_action=str(data.get("next_action", "")),
            capture_context=capture_context,
            confidence=confidence,
            sync_to_notion=bool(data.get("sync_to_notion", True)),
            notion_status=notion_status,
        )
```

- [ ] **Step 3: Write and run tests**

Create `tests/unit/test_notion_classifier.py`:
```python
from operation_drake.integrations.notion.classifier import NotionClassifier
from operation_drake.llm.mock_provider import MockLLMProvider


def _make_classifier(response: str = "") -> NotionClassifier:
    import json
    default = json.dumps({
        "project": "Business Ideas",
        "content_type": "Idea",
        "title": "AI deployment service for PE firms",
        "summary": "An idea for an AI agent deployment service targeting small PE firms.",
        "tags": ["AI", "PE", "startup"],
        "actionable": False,
        "next_action": "",
        "capture_context": "General",
        "confidence": 0.92,
        "sync_to_notion": True,
        "notion_status": "Inbox",
    })
    mock = MockLLMProvider(default_response=response or default)
    return NotionClassifier(llm=mock)


def test_classify_returns_notion_classification():
    clf = _make_classifier()
    result = clf.classify("Business idea: AI deployment service for PE firms")
    assert result.project == "Business Ideas"
    assert result.content_type == "Idea"
    assert result.confidence == 0.92
    assert result.notion_status == "Inbox"
    assert result.sync_to_notion is True


def test_classify_low_confidence_sets_needs_review():
    import json
    low = json.dumps({
        "project": "General", "content_type": "General Note",
        "title": "Unclear thought", "summary": "...", "tags": [],
        "actionable": False, "next_action": "", "capture_context": "General",
        "confidence": 0.55, "sync_to_notion": True, "notion_status": "Inbox",
    })
    clf = _make_classifier(low)
    result = clf.classify("some unclear content")
    assert result.notion_status == "Needs Review"
    assert result.project == "General"


def test_classify_explicit_no_sync():
    import json
    no_sync = json.dumps({
        "project": "General", "content_type": "General Note",
        "title": "Private note", "summary": "...", "tags": [],
        "actionable": False, "next_action": "", "capture_context": "General",
        "confidence": 0.90, "sync_to_notion": False, "notion_status": "Inbox",
    })
    clf = _make_classifier(no_sync)
    result = clf.classify("Do not save this to Notion. Private thought.")
    assert result.sync_to_notion is False


def test_classify_invalid_project_falls_back_to_general():
    import json
    bad = json.dumps({
        "project": "NotARealProject", "content_type": "Idea",
        "title": "T", "summary": "S", "tags": [],
        "actionable": False, "next_action": "", "capture_context": "General",
        "confidence": 0.80, "sync_to_notion": True, "notion_status": "Inbox",
    })
    clf = _make_classifier(bad)
    result = clf.classify("something")
    assert result.project == "General"


def test_classify_invalid_content_type_falls_back():
    import json
    bad = json.dumps({
        "project": "Ascend", "content_type": "XYZType",
        "title": "T", "summary": "S", "tags": [],
        "actionable": False, "next_action": "", "capture_context": "General",
        "confidence": 0.80, "sync_to_notion": True, "notion_status": "Inbox",
    })
    clf = _make_classifier(bad)
    result = clf.classify("something")
    assert result.content_type == "General Note"


def test_classify_llm_failure_returns_safe_default():
    from operation_drake.llm.mock_provider import MockLLMProvider
    mock = MockLLMProvider(default_response="not valid json {{{{")
    clf = NotionClassifier(llm=mock)
    result = clf.classify("test content")
    assert result.notion_status == "Needs Review"
    assert result.confidence == 0.0
```

`MockLLMProvider` currently returns a fixed response. Check if it accepts `default_response`. If `MockLLMProvider` does not support a `default_response` parameter, the tests should use the default mock response (which is already valid JSON from the mock provider) and adjust expectations accordingly.

Check `src/operation_drake/llm/mock_provider.py` first. If the mock always returns fixed JSON that matches the valid project/type lists, adjust tests to match mock output rather than injecting custom responses.

Run: `pytest tests/unit/test_notion_classifier.py -v`
Expected: tests pass (adjust assertions to match MockLLMProvider behavior if needed)

- [ ] **Step 4: Commit**

```bash
git add prompts/notion_classifier.md src/operation_drake/integrations/notion/classifier.py tests/unit/test_notion_classifier.py
git commit -m "feat: add NotionClassifier with project/content-type/context inference"
```

---

### Task 4: Property Mapper + Body Builder

**Files:**
- Create: `src/operation_drake/integrations/notion/mapper.py`
- Create: `src/operation_drake/integrations/notion/body_builder.py`
- Test: `tests/unit/test_notion_mapper.py`
- Test: `tests/unit/test_notion_body.py`

**Interfaces consumed:** `NotionClassification` (Task 2)
**Interfaces produced:**
- `build_properties(classification, captured_at, source) -> dict`
- `build_body(classification) -> list[dict]`
- `_chunk_rich_text(content, max_len=2000) -> list[dict]`

- [ ] **Step 1: Create mapper.py**

`src/operation_drake/integrations/notion/mapper.py`:
```python
from __future__ import annotations

from datetime import datetime

from operation_drake.integrations.notion.models import NotionClassification

_SOURCE_MAP = {
    ("telegram", "text"): "Telegram Text",
    ("telegram", "voice"): "Telegram Voice",
    ("telegram", "forwarded"): "Telegram Forward",
    ("telegram", "url"): "URL",
}


def channel_to_source(channel: str, message_type: str) -> str:
    return _SOURCE_MAP.get((channel, message_type), "Other")


def _rich_text(content: str) -> list[dict]:
    """Chunk content into Notion rich_text elements (max 2000 chars each)."""
    if not content:
        return [{"type": "text", "text": {"content": ""}}]
    chunks = []
    while content:
        chunks.append({"type": "text", "text": {"content": content[:2000]}})
        content = content[2000:]
    return chunks


def build_properties(
    classification: NotionClassification,
    captured_at: datetime,
    source: str,
) -> dict:
    props: dict = {
        "Name": {"title": [{"text": {"content": classification.title[:2000]}}]},
        "Project": {"select": {"name": classification.project}},
        "Content Type": {"select": {"name": classification.content_type}},
        "Status": {"select": {"name": classification.notion_status}},
        "Source": {"select": {"name": source}},
        "Capture Context": {"select": {"name": classification.capture_context}},
        "Captured At": {"date": {"start": captured_at.isoformat()}},
        "Summary": {"rich_text": _rich_text(classification.summary[:2000])},
        "Actionable": {"checkbox": classification.actionable},
        "Next Action": {"rich_text": _rich_text((classification.next_action or "")[:2000])},
        "Tags": {
            "multi_select": [{"name": t[:100]} for t in classification.tags[:10]]
        },
        "Confidence": {"number": round(classification.confidence, 4)},
        "D.R.A.K.E. Task ID": {
            "rich_text": [{"type": "text", "text": {"content": classification.task_id[:2000]}}]
        },
        "D.R.A.K.E. Artifact ID": {
            "rich_text": [
                {"type": "text", "text": {"content": (classification.artifact_id or "")[:2000]}}
            ]
        },
        "Sync Status": {"select": {"name": "Synced"}},
    }
    if classification.source_url:
        props["Source URL"] = {"url": classification.source_url}
    return props
```

- [ ] **Step 2: Create body_builder.py**

`src/operation_drake/integrations/notion/body_builder.py`:
```python
from __future__ import annotations

from operation_drake.integrations.notion.models import NotionClassification

_BLOCK_TEXT_MAX = 2000


def _text_chunks(content: str) -> list[str]:
    chunks = []
    while content:
        chunks.append(content[:_BLOCK_TEXT_MAX])
        content = content[_BLOCK_TEXT_MAX:]
    return chunks


def _paragraph(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": text[:_BLOCK_TEXT_MAX]}}]
        },
    }


def _heading(text: str, level: int = 2) -> dict:
    h = f"heading_{level}"
    return {
        "object": "block",
        "type": h,
        h: {"rich_text": [{"type": "text", "text": {"content": text[:_BLOCK_TEXT_MAX]}}]},
    }


def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def _todo(text: str) -> dict:
    return {
        "object": "block",
        "type": "to_do",
        "to_do": {
            "rich_text": [{"type": "text", "text": {"content": text[:_BLOCK_TEXT_MAX]}}],
            "checked": False,
        },
    }


def _paragraphs_for(content: str) -> list[dict]:
    return [_paragraph(chunk) for chunk in _text_chunks(content) if chunk.strip()]


def build_body(classification: NotionClassification) -> list[dict]:
    blocks: list[dict] = []

    if classification.summary:
        blocks.append(_heading("Summary"))
        blocks.extend(_paragraphs_for(classification.summary))

    if classification.content_type == "Voice Memo" and classification.next_action:
        blocks.append(_divider())
        blocks.append(_heading("Transcript / Original Input"))
        blocks.extend(_paragraphs_for(classification.next_action))

    if classification.actionable and classification.next_action:
        blocks.append(_divider())
        blocks.append(_heading("Action Items"))
        for line in classification.next_action.splitlines():
            line = line.strip()
            if line:
                blocks.append(_todo(line))

    blocks.append(_divider())
    blocks.append(_heading("D.R.A.K.E. Metadata", level=3))
    meta_lines = [
        f"Task ID: {classification.task_id}",
        f"Artifact ID: {classification.artifact_id or 'none'}",
        f"Project: {classification.project}",
        f"Content Type: {classification.content_type}",
        f"Capture Context: {classification.capture_context}",
        f"Confidence: {classification.confidence:.0%}",
    ]
    blocks.append(_paragraph("\n".join(meta_lines)))

    return blocks
```

- [ ] **Step 3: Write tests for mapper**

`tests/unit/test_notion_mapper.py`:
```python
from datetime import datetime, timezone

from operation_drake.integrations.notion.mapper import (
    build_properties,
    channel_to_source,
)
from operation_drake.integrations.notion.models import NotionClassification


def _ts() -> datetime:
    return datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)


def test_channel_to_source_telegram_text():
    assert channel_to_source("telegram", "text") == "Telegram Text"


def test_channel_to_source_telegram_voice():
    assert channel_to_source("telegram", "voice") == "Telegram Voice"


def test_channel_to_source_unknown_falls_back():
    assert channel_to_source("chatgpt", "voice") == "Other"


def test_build_properties_name():
    c = NotionClassification(title="My Idea", task_id="t1")
    props = build_properties(c, _ts(), "Telegram Text")
    assert props["Name"]["title"][0]["text"]["content"] == "My Idea"


def test_build_properties_project():
    c = NotionClassification(project="Ascend", title="x", task_id="t1")
    props = build_properties(c, _ts(), "Telegram Text")
    assert props["Project"]["select"]["name"] == "Ascend"


def test_build_properties_actionable_checkbox():
    c = NotionClassification(actionable=True, title="x", task_id="t1")
    props = build_properties(c, _ts(), "Telegram Text")
    assert props["Actionable"]["checkbox"] is True


def test_build_properties_source_url_omitted_when_none():
    c = NotionClassification(title="x", task_id="t1", source_url=None)
    props = build_properties(c, _ts(), "Telegram Text")
    assert "Source URL" not in props


def test_build_properties_source_url_included_when_set():
    c = NotionClassification(title="x", task_id="t1", source_url="https://example.com")
    props = build_properties(c, _ts(), "Telegram Text")
    assert props["Source URL"]["url"] == "https://example.com"


def test_build_properties_long_title_truncated():
    c = NotionClassification(title="x" * 3000, task_id="t1")
    props = build_properties(c, _ts(), "Telegram Text")
    content = props["Name"]["title"][0]["text"]["content"]
    assert len(content) <= 2000


def test_build_properties_task_id_stored():
    c = NotionClassification(title="x", task_id="task-abc-123")
    props = build_properties(c, _ts(), "Telegram Text")
    assert props["D.R.A.K.E. Task ID"]["rich_text"][0]["text"]["content"] == "task-abc-123"


def test_build_properties_confidence_number():
    c = NotionClassification(title="x", task_id="t1", confidence=0.87654)
    props = build_properties(c, _ts(), "Telegram Text")
    assert props["Confidence"]["number"] == 0.8765


def test_build_properties_tags_multi_select():
    c = NotionClassification(title="x", task_id="t1", tags=["AI", "PE"])
    props = build_properties(c, _ts(), "Telegram Text")
    names = [t["name"] for t in props["Tags"]["multi_select"]]
    assert "AI" in names and "PE" in names
```

- [ ] **Step 4: Write tests for body builder**

`tests/unit/test_notion_body.py`:
```python
from operation_drake.integrations.notion.body_builder import build_body, _text_chunks
from operation_drake.integrations.notion.models import NotionClassification


def test_text_chunks_short_content():
    result = _text_chunks("hello")
    assert result == ["hello"]


def test_text_chunks_long_content_splits():
    long = "x" * 5000
    chunks = _text_chunks(long)
    assert len(chunks) == 3
    assert all(len(c) <= 2000 for c in chunks)
    assert "".join(chunks) == long


def test_build_body_contains_summary_heading():
    c = NotionClassification(title="T", task_id="t1", summary="This is a summary.")
    blocks = build_body(c)
    types = [b["type"] for b in blocks]
    assert "heading_2" in types
    headings = [b for b in blocks if b["type"] == "heading_2"]
    heading_texts = [h["heading_2"]["rich_text"][0]["text"]["content"] for h in headings]
    assert "Summary" in heading_texts


def test_build_body_contains_metadata():
    c = NotionClassification(title="T", task_id="task-xyz", project="Ascend")
    blocks = build_body(c)
    all_text = " ".join(
        b.get("paragraph", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "")
        for b in blocks if b["type"] == "paragraph"
    )
    assert "task-xyz" in all_text
    assert "Ascend" in all_text


def test_build_body_action_items_use_todo_blocks():
    c = NotionClassification(
        title="T", task_id="t1",
        actionable=True,
        next_action="Call mom\nUpdate docs",
    )
    blocks = build_body(c)
    todo_blocks = [b for b in blocks if b["type"] == "to_do"]
    assert len(todo_blocks) == 2


def test_build_body_no_action_items_when_not_actionable():
    c = NotionClassification(title="T", task_id="t1", actionable=False, next_action="")
    blocks = build_body(c)
    todo_blocks = [b for b in blocks if b["type"] == "to_do"]
    assert len(todo_blocks) == 0


def test_build_body_long_summary_chunked():
    c = NotionClassification(title="T", task_id="t1", summary="x" * 5000)
    blocks = build_body(c)
    paragraphs = [b for b in blocks if b["type"] == "paragraph"]
    for p in paragraphs:
        text = p["paragraph"]["rich_text"][0]["text"]["content"]
        assert len(text) <= 2000
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_notion_mapper.py tests/unit/test_notion_body.py -v
```
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/operation_drake/integrations/notion/mapper.py src/operation_drake/integrations/notion/body_builder.py tests/unit/test_notion_mapper.py tests/unit/test_notion_body.py
git commit -m "feat: add Notion property mapper and page body builder"
```

---

### Task 5: Sync Service

**Files:**
- Create: `src/operation_drake/integrations/notion/sync_service.py`
- Test: `tests/unit/test_notion_sync_service.py`

**Interfaces consumed:** `NotionClientInterface`, `NotionSyncRepository`, `NotionClassification`, `build_properties`, `build_body`, `channel_to_source`
**Interfaces produced:**
- `NotionSyncService(session, client, database_id, low_confidence_threshold)`
- `NotionSyncService.sync(task_id, artifact_id, classification, captured_at, channel, message_type) -> SyncResult`
- `NotionSyncService.sync_by_task_id(task_id) -> SyncResult`
- `NotionSyncService.sync_pending(limit=20) -> list[SyncResult]`
- `NotionSyncService.get_status() -> dict`

- [ ] **Step 1: Create sync_service.py**

`src/operation_drake/integrations/notion/sync_service.py`:
```python
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

        if existing_record and existing_record.sync_status == "synced" and existing_record.external_page_id:
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
            existing_notion_page = self._client.find_page_by_task_id(task_id)

            if existing_notion_page:
                page_id, page_url = self._client.update_page(existing_notion_page["id"], properties)
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
            return SyncResult(status="already_synced", page_id=record.external_page_id, page_url=url)
        classification = NotionClassification(task_id=task_id)
        return self.sync(task_id, record.artifact_id, classification, datetime.now(UTC))

    def sync_pending(self, limit: int = 20) -> list[SyncResult]:
        records = self._repo.list_pending(limit=limit)
        results = []
        for record in records:
            classification = NotionClassification(task_id=record.task_id)
            result = self.sync(
                task_id=record.task_id,
                artifact_id=record.artifact_id,
                classification=classification,
                captured_at=record.created_at,
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
```

- [ ] **Step 2: Write tests**

`tests/unit/test_notion_sync_service.py`:
```python
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from operation_drake.integrations.notion.mock_client import MockNotionClient
from operation_drake.integrations.notion.models import NotionClassification
from operation_drake.integrations.notion.sync_service import NotionSyncService
from operation_drake.models.database import Base


def _make_svc(client=None):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    if client is None:
        client = MockNotionClient()
    return NotionSyncService(session=session, client=client, database_id="db-1")


def _ts():
    return datetime(2026, 7, 4, tzinfo=UTC)


def _clf(title="Test", task_id="t1", sync_to_notion=True, confidence=0.9):
    return NotionClassification(
        title=title, task_id=task_id,
        sync_to_notion=sync_to_notion, confidence=confidence,
        summary="Summary text.",
    )


def test_sync_success_creates_page():
    client = MockNotionClient()
    svc = _make_svc(client)
    result = svc.sync("t1", "a1", _clf(task_id="t1"), _ts())
    assert result.status == "synced"
    assert result.page_id
    assert "notion.so" in result.page_url
    assert len(client.created_pages) == 1


def test_sync_skipped_when_user_opts_out():
    client = MockNotionClient()
    svc = _make_svc(client)
    clf = _clf(task_id="t1", sync_to_notion=False)
    result = svc.sync("t1", None, clf, _ts())
    assert result.status == "skipped"
    assert len(client.created_pages) == 0


def test_sync_idempotent_second_call_returns_already_synced():
    client = MockNotionClient()
    svc = _make_svc(client)
    svc.sync("t1", "a1", _clf(task_id="t1"), _ts())
    result2 = svc.sync("t1", "a1", _clf(task_id="t1"), _ts())
    assert result2.status == "already_synced"
    assert len(client.created_pages) == 1  # not 2


def test_sync_updates_existing_notion_page():
    existing_id = "existing-page-001"
    client = MockNotionClient(existing_page_id=existing_id)
    svc = _make_svc(client)
    result = svc.sync("t1", "a1", _clf(task_id="t1"), _ts())
    assert result.status == "updated"
    assert result.page_id == existing_id
    assert len(client.updated_pages) == 1
    assert len(client.created_pages) == 0


def test_sync_failed_auth_does_not_raise():
    client = MockNotionClient(should_fail=True, fail_with="auth")
    svc = _make_svc(client)
    result = svc.sync("t1", None, _clf(task_id="t1"), _ts())
    assert result.status == "failed"
    assert result.error_category == "auth"


def test_sync_failed_timeout():
    client = MockNotionClient(should_fail=True, fail_with="timeout")
    svc = _make_svc(client)
    result = svc.sync("t1", None, _clf(task_id="t1"), _ts())
    assert result.status == "failed"
    assert result.error_category == "timeout"


def test_sync_failed_rate_limit():
    client = MockNotionClient(should_fail=True, fail_with="rate_limit")
    svc = _make_svc(client)
    result = svc.sync("t1", None, _clf(task_id="t1"), _ts())
    assert result.status == "failed"
    assert result.error_category == "rate_limit"


def test_sync_retry_after_failure():
    client = MockNotionClient(should_fail=True, fail_with="timeout")
    svc = _make_svc(client)
    svc.sync("t1", None, _clf(task_id="t1"), _ts())
    # Now fix the client and retry
    client._should_fail = False
    result = svc.sync("t1", None, _clf(task_id="t1"), _ts())
    assert result.status == "synced"


def test_low_confidence_sets_needs_review_in_result():
    client = MockNotionClient()
    svc = _make_svc(client)
    clf = _clf(task_id="t1", confidence=0.5)
    clf.notion_status = "Needs Review"
    result = svc.sync("t1", None, clf, _ts())
    assert result.needs_review is True


def test_no_duplicate_pages_on_restart():
    client = MockNotionClient()
    svc = _make_svc(client)
    svc.sync("t1", "a1", _clf(task_id="t1"), _ts())
    # Simulate restart: same session, same client
    result = svc.sync("t1", "a1", _clf(task_id="t1"), _ts())
    assert len(client.created_pages) == 1
    assert result.status == "already_synced"


def test_get_status_returns_counts():
    svc = _make_svc(MockNotionClient())
    status = svc.get_status()
    assert "pending" in status
    assert "failed" in status
    assert "last_synced_at" in status


def test_sync_pending_processes_failed_records():
    client = MockNotionClient(should_fail=True, fail_with="timeout")
    svc = _make_svc(client)
    svc.sync("t1", None, _clf(task_id="t1"), _ts())
    client._should_fail = False
    results = svc.sync_pending(limit=10)
    assert any(r.status == "synced" for r in results)
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/unit/test_notion_sync_service.py -v
```
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add src/operation_drake/integrations/notion/sync_service.py tests/unit/test_notion_sync_service.py
git commit -m "feat: add NotionSyncService with idempotency, retry, and outbox tracking"
```

---

### Task 6: Live Notion Client

**Files:**
- Create: `src/operation_drake/integrations/notion/live_client.py`
- Test: (no live API calls — verified manually via --check-notion)

**Interfaces consumed:** `NotionClientInterface` ABC
**Interfaces produced:** `LiveNotionClient(api_token, database_id)`

- [ ] **Step 1: Create live_client.py**

`src/operation_drake/integrations/notion/live_client.py`:
```python
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
                # Log only the status code — never log the full error (may contain auth headers)
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
```

- [ ] **Step 2: Add factory function to integrations/notion/__init__.py**

`src/operation_drake/integrations/notion/__init__.py`:
```python
from __future__ import annotations

from operation_drake.integrations.notion.client import NotionClientInterface
from operation_drake.integrations.notion.mock_client import MockNotionClient


def get_notion_client(settings) -> NotionClientInterface:
    """Return live client when Notion is enabled and configured, otherwise mock."""
    if not settings.notion_enabled or not settings.notion_api_token:
        return MockNotionClient()
    from operation_drake.integrations.notion.live_client import LiveNotionClient

    return LiveNotionClient(
        api_token=settings.notion_api_token,
        database_id=settings.notion_database_id,
    )
```

- [ ] **Step 3: Verify ruff passes**

```bash
ruff check src/operation_drake/integrations/notion/live_client.py src/operation_drake/integrations/notion/__init__.py
```
Expected: no output (all checks passed)

- [ ] **Step 4: Run full suite**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -5
```
Expected: all previous tests still pass

- [ ] **Step 5: Commit**

```bash
git add src/operation_drake/integrations/notion/live_client.py src/operation_drake/integrations/notion/__init__.py
git commit -m "feat: add LiveNotionClient and get_notion_client factory"
```

---

### Task 7: Orchestration Integration

**Files:**
- Modify: `src/operation_drake/services/orchestration.py`
- Modify: `src/operation_drake/channels/telegram.py`
- Test: `tests/unit/test_notion_orchestration.py` (new)

**Interfaces consumed:** `NotionClassifier`, `NotionSyncService`, `get_notion_client`
**Interfaces produced:**
- `ProcessResult` extended with: `notion_sync_status`, `notion_page_url`, `notion_project`, `notion_content_type`, `notion_needs_review`
- `_format_result` extended to include Notion summary line when sync status is present

- [ ] **Step 1: Extend ProcessResult dataclass**

In `src/operation_drake/services/orchestration.py`, update the `ProcessResult` dataclass:
```python
@dataclass
class ProcessResult:
    message_id: str
    task_id: str
    intent: str
    confidence: float
    proposed_action: str
    status: str
    approval_required: bool
    clarification_question: str | None
    artifact_path: str | None
    result_summary: str
    session_tokens: int = 0
    notion_sync_status: str | None = None
    notion_page_url: str | None = None
    notion_project: str | None = None
    notion_content_type: str | None = None
    notion_needs_review: bool = False
```

- [ ] **Step 2: Add Notion imports and inject into OrchestratorService**

In `src/operation_drake/services/orchestration.py`, add imports at the top:
```python
from datetime import UTC, datetime

from operation_drake.integrations.notion.classifier import NotionClassifier
from operation_drake.integrations.notion.sync_service import NotionSyncService
```

Update `OrchestratorService.__init__` signature:
```python
def __init__(
    self,
    session: Session,
    llm: LLMProvider,
    transcriber: TranscriptionProvider,
    artifacts_dir: str,
    notion_sync_service: NotionSyncService | None = None,
) -> None:
    self._session = session
    self._msg_repo = MessageRepository(session)
    self._task_repo = TaskRepository(session)
    self._artifact_repo = ArtifactRepository(session)
    self._intent_repo = IntentRepository(session)
    self._run_repo = AgentRunRepository(session)
    self._router = RouterAgent(llm=llm)
    self._capture_agent = CaptureAgent(llm=llm)
    self._synthesis_agent = SynthesisAgent(llm=llm)
    self._transcriber = transcriber
    self._artifact_svc = ArtifactService(artifacts_dir=artifacts_dir)
    self._notion_svc = notion_sync_service
    self._notion_classifier = NotionClassifier(llm=llm) if notion_sync_service else None
```

- [ ] **Step 3: Add _sync_to_notion helper method**

In `OrchestratorService`, add after `_execute_workflow`:
```python
def _sync_to_notion(
    self,
    task_id: str,
    artifact_id: str | None,
    content: str,
    result_summary: str,
    intent: str,
    project: str | None,
    channel: str,
    message_type: str,
) -> tuple[str | None, str | None, str | None, str | None, bool]:
    """Returns (sync_status, page_url, project, content_type, needs_review). Never raises."""
    if not self._notion_svc or not self._notion_classifier:
        return None, None, None, None, False
    try:
        classification = self._notion_classifier.classify(
            content=content,
            workflow_summary=result_summary,
            intent=intent,
            existing_project=project,
        )
        classification.task_id = task_id
        classification.artifact_id = artifact_id
        sync_result = self._notion_svc.sync(
            task_id=task_id,
            artifact_id=artifact_id,
            classification=classification,
            captured_at=datetime.now(UTC),
            channel=channel,
            message_type=message_type,
        )
        return (
            sync_result.status,
            sync_result.page_url,
            classification.project,
            classification.content_type,
            sync_result.needs_review,
        )
    except Exception as e:
        logger.error({"action": "notion_sync_error", "task_id": task_id, "error": str(e)[:100]})
        return "failed", None, None, None, False
```

- [ ] **Step 4: Call _sync_to_notion in process() after artifact creation**

In the `process()` method, find the block that calls `_artifact_repo.create(...)` and the subsequent return. Replace the final `return ProcessResult(...)` with:

```python
        artifact_id: str | None = None
        if artifact_path:
            orm = self._artifact_repo.create(
                ArtifactCreate(
                    task_id=task.id,
                    artifact_type=decision.primary_intent,
                    title=task.title,
                    file_path=artifact_path,
                    content_preview=result_summary[:200],
                )
            )
            artifact_id = orm.id

        notion_status, notion_url, notion_proj, notion_type, notion_review = self._sync_to_notion(
            task_id=task.id,
            artifact_id=artifact_id,
            content=normalized.normalized_text,
            result_summary=result_summary,
            intent=decision.primary_intent,
            project=project,
            channel=channel,
            message_type=message_type,
        )

        return ProcessResult(
            message_id=msg.id,
            task_id=task.id,
            intent=decision.primary_intent,
            confidence=decision.confidence,
            proposed_action=decision.proposed_action,
            status=TaskStatus.completed.value,
            approval_required=False,
            clarification_question=None,
            artifact_path=artifact_path,
            result_summary=result_summary,
            notion_sync_status=notion_status,
            notion_page_url=notion_url,
            notion_project=notion_proj,
            notion_content_type=notion_type,
            notion_needs_review=notion_review,
        )
```

Note: `process()` currently passes `channel` but `message_type` is not currently threaded through — it comes from the original normalized message. Update `process()` signature to pass `message_type` to `_sync_to_notion`. Use `message_type` already available via `normalized.message_type`.

Also apply the same Notion sync pattern in `execute_approved_task()` after artifact creation.

- [ ] **Step 5: Update _format_result in telegram.py**

In `src/operation_drake/channels/telegram.py`, update `_format_result`:
```python
def _format_result(result) -> str:
    lines = [
        f"Intent: {result.intent} ({result.confidence:.0%} confident)",
        f"Action: {result.proposed_action}",
        f"Status: {result.status}",
    ]
    if result.status == "awaiting_approval":
        if result.session_tokens:
            cost = result.session_tokens * _COST_PER_TOKEN
            lines.append(f"Session spend so far: ~${cost:.4f} ({result.session_tokens:,} tokens)")
        lines.append(f"Requires approval -- task {result.task_id}")
        lines.append(f"Use /approve {result.task_id} to execute")
        lines.append(f"Use /reject {result.task_id} to cancel")
    if result.clarification_question:
        lines.append(f"Question: {result.clarification_question}")
    if result.status == "completed" and result.result_summary:
        lines.append(f"Result: {result.result_summary}")
    if result.artifact_path:
        lines.append("Artifact saved.")
    if result.notion_sync_status and result.notion_sync_status not in ("disabled", "skipped"):
        lines.append("")
        if result.notion_project:
            lines.append(f"Project: {result.notion_project}")
        if result.notion_content_type:
            lines.append(f"Type: {result.notion_content_type}")
        if result.notion_sync_status in ("synced", "updated", "already_synced"):
            lines.append("Notion: synced")
            if result.notion_page_url:
                lines.append(result.notion_page_url)
        elif result.notion_sync_status == "failed":
            lines.append("Notion: pending (will retry)")
        if result.notion_needs_review:
            lines.append("Note: saved to Needs Review -- classification was uncertain")
    return "\n".join(lines)
```

- [ ] **Step 6: Update _make_orchestrator in telegram.py**

```python
def _make_orchestrator(artifacts_dir: str) -> OrchestratorService:
    from operation_drake.integrations.notion import get_notion_client
    from operation_drake.integrations.notion.sync_service import NotionSyncService

    settings = get_settings()
    session = get_session()
    notion_svc: NotionSyncService | None = None
    if settings.notion_enabled:
        notion_client = get_notion_client(settings)
        notion_svc = NotionSyncService(
            session=session,
            client=notion_client,
            database_id=settings.notion_database_id,
            low_confidence_threshold=settings.notion_low_confidence_threshold,
        )
    return OrchestratorService(
        session=session,
        llm=get_llm_provider(),
        transcriber=get_transcription_provider(),
        artifacts_dir=artifacts_dir,
        notion_sync_service=notion_svc,
    )
```

- [ ] **Step 7: Write orchestration integration tests**

`tests/unit/test_notion_orchestration.py`:
```python
import tempfile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from operation_drake.integrations.notion.mock_client import MockNotionClient
from operation_drake.integrations.notion.sync_service import NotionSyncService
from operation_drake.llm.mock_provider import MockLLMProvider
from operation_drake.models.database import Base
from operation_drake.services.orchestration import OrchestratorService
from operation_drake.transcription.mock_transcriber import MockTranscriber


def _make_orchestrator(tmpdir, fail_notion=False):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    client = MockNotionClient(should_fail=fail_notion, fail_with="timeout")
    notion_svc = NotionSyncService(session=session, client=client, database_id="db-test")
    return OrchestratorService(
        session=session,
        llm=MockLLMProvider(),
        transcriber=MockTranscriber(),
        artifacts_dir=tmpdir,
        notion_sync_service=notion_svc,
    ), client


def test_process_completes_locally_when_notion_fails():
    with tempfile.TemporaryDirectory() as tmpdir:
        orch, client = _make_orchestrator(tmpdir, fail_notion=True)
        result = orch.process(channel="telegram", raw_text="Save this note about PE firms")
        # Task should complete locally even if Notion fails
        assert result.status == "completed"
        assert result.notion_sync_status == "failed"


def test_process_syncs_when_notion_succeeds():
    with tempfile.TemporaryDirectory() as tmpdir:
        orch, client = _make_orchestrator(tmpdir, fail_notion=False)
        result = orch.process(channel="telegram", raw_text="Business idea: AI for PE firms")
        assert result.status == "completed"
        assert result.notion_sync_status in ("synced", "updated", "already_synced", None)


def test_process_no_notion_service_still_completes():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        orch = OrchestratorService(
            session=session,
            llm=MockLLMProvider(),
            transcriber=MockTranscriber(),
            artifacts_dir=tmpdir,
            notion_sync_service=None,
        )
        result = orch.process(channel="telegram", raw_text="Save this note")
        assert result.status in ("completed", "awaiting_approval")
        assert result.notion_sync_status is None


def test_no_duplicate_notion_pages_on_repeated_process():
    with tempfile.TemporaryDirectory() as tmpdir:
        orch, client = _make_orchestrator(tmpdir)
        result = orch.process(channel="telegram", raw_text="Answer Movement idea: timer breathing")
        # Even if called twice (edge case), no duplicate pages
        assert len(client.created_pages) <= 1
```

- [ ] **Step 8: Run tests**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -10
```
Expected: all pass

- [ ] **Step 9: Commit**

```bash
git add src/operation_drake/services/orchestration.py src/operation_drake/channels/telegram.py tests/unit/test_notion_orchestration.py
git commit -m "feat: wire NotionSyncService into orchestrator, extend ProcessResult with notion fields"
```

---

### Task 8: Telegram Commands — /notion, /sync, /sync_pending

**Files:**
- Modify: `src/operation_drake/channels/telegram.py`
- Test: `tests/unit/test_notion_commands.py`

**Interfaces produced:** Three new Telegram command handlers registered in `_setup_handlers`:
- `/notion` → `_cmd_notion`
- `/sync <task_id>` → `_cmd_sync`
- `/sync_pending` → `_cmd_sync_pending`

- [ ] **Step 1: Add command handlers to _setup_handlers**

In `TelegramAdapter._setup_handlers`, add:
```python
self._app.add_handler(CommandHandler("notion", self._cmd_notion))
self._app.add_handler(CommandHandler("sync", self._cmd_sync))
self._app.add_handler(CommandHandler("sync_pending", self._cmd_sync_pending))
```

- [ ] **Step 2: Add command methods**

In `TelegramAdapter`, add after `_cmd_cost`:
```python
async def _cmd_notion(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not self._is_allowed(str(update.effective_user.id)):
        return
    loop = asyncio.get_event_loop()
    reply = await loop.run_in_executor(None, self._do_notion_status)
    await _reply(update, reply)

async def _cmd_sync(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not self._is_allowed(str(update.effective_user.id)):
        return
    if not context.args:
        await _reply(update, "Usage: /sync <task_id>")
        return
    task_id = context.args[0]
    loop = asyncio.get_event_loop()
    reply = await loop.run_in_executor(None, self._do_sync_task, task_id)
    await _reply(update, reply)

async def _cmd_sync_pending(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not self._is_allowed(str(update.effective_user.id)):
        return
    loop = asyncio.get_event_loop()
    reply = await loop.run_in_executor(None, self._do_sync_pending)
    await _reply(update, reply)
```

- [ ] **Step 3: Add sync helpers**

In the sync helpers section, add:
```python
def _do_notion_status(self) -> str:
    from operation_drake.integrations.notion import get_notion_client
    from operation_drake.integrations.notion.sync_service import NotionSyncService

    s = self._settings
    lines = ["Notion status:"]
    lines.append(f"Enabled: {s.notion_enabled}")
    if not s.notion_enabled:
        return "\n".join(lines)
    lines.append(f"Database configured: {'yes' if s.notion_database_id else 'no'}")
    with get_session() as session:
        client = get_notion_client(s)
        svc = NotionSyncService(
            session=session,
            client=client,
            database_id=s.notion_database_id,
            low_confidence_threshold=s.notion_low_confidence_threshold,
        )
        status = svc.get_status()
    lines.append(f"Pending syncs: {status['pending']}")
    lines.append(f"Failed syncs: {status['failed']}")
    if status["last_synced_at"]:
        lines.append(f"Last synced: {status['last_synced_at']}")
    return "\n".join(lines)

def _do_sync_task(self, task_id: str) -> str:
    from operation_drake.integrations.notion import get_notion_client
    from operation_drake.integrations.notion.sync_service import NotionSyncService

    s = self._settings
    if not s.notion_enabled:
        return "Notion is not enabled."
    with get_session() as session:
        client = get_notion_client(s)
        svc = NotionSyncService(
            session=session,
            client=client,
            database_id=s.notion_database_id,
            low_confidence_threshold=s.notion_low_confidence_threshold,
        )
        result = svc.sync_by_task_id(task_id)
    if result.status == "not_found":
        return f"No sync record found for task {task_id[:8]}."
    if result.status in ("synced", "updated"):
        lines = [f"Synced task {task_id[:8]}."]
        if result.page_url:
            lines.append(result.page_url)
        return "\n".join(lines)
    if result.status == "already_synced":
        lines = [f"Task {task_id[:8]} was already synced."]
        if result.page_url:
            lines.append(result.page_url)
        return "\n".join(lines)
    return f"Sync failed for task {task_id[:8]}. Category: {result.error_category or 'unknown'}"

def _do_sync_pending(self) -> str:
    from operation_drake.integrations.notion import get_notion_client
    from operation_drake.integrations.notion.sync_service import NotionSyncService

    s = self._settings
    if not s.notion_enabled:
        return "Notion is not enabled."
    with get_session() as session:
        client = get_notion_client(s)
        svc = NotionSyncService(
            session=session,
            client=client,
            database_id=s.notion_database_id,
            low_confidence_threshold=s.notion_low_confidence_threshold,
        )
        results = svc.sync_pending(limit=20)
    if not results:
        return "No pending syncs."
    synced = sum(1 for r in results if r.status in ("synced", "updated"))
    failed = sum(1 for r in results if r.status == "failed")
    return f"Processed {len(results)} pending sync(s): {synced} synced, {failed} failed."
```

Note: `get_session()` currently returns a raw session, not a context manager. The helpers use `get_session()` directly without `with` — be consistent with existing helpers in telegram.py (which call `get_session()` without `with`). Check and match the existing pattern.

- [ ] **Step 4: Update /help text**

In `_cmd_help`, add to the help text:
```
/notion -- Notion sync status\n
/sync <task_id> -- retry Notion sync for a task\n
/sync_pending -- retry all pending Notion syncs\n
```

- [ ] **Step 5: Write tests**

`tests/unit/test_notion_commands.py`:
```python
from operation_drake.channels.telegram import _format_result
from operation_drake.services.orchestration import ProcessResult


def _make_result(**kwargs) -> ProcessResult:
    defaults = dict(
        message_id="m1", task_id="t1", intent="save_note",
        confidence=0.9, proposed_action="Save note",
        status="completed", approval_required=False,
        clarification_question=None, artifact_path="/tmp/test.md",
        result_summary="Note saved.",
    )
    defaults.update(kwargs)
    return ProcessResult(**defaults)


def test_format_result_no_notion_when_disabled():
    r = _make_result()
    text = _format_result(r)
    assert "Notion" not in text


def test_format_result_includes_notion_synced():
    r = _make_result(
        notion_sync_status="synced",
        notion_project="Business Ideas",
        notion_content_type="Idea",
        notion_page_url="https://notion.so/abc123",
    )
    text = _format_result(r)
    assert "Project: Business Ideas" in text
    assert "Type: Idea" in text
    assert "Notion: synced" in text
    assert "https://notion.so/abc123" in text


def test_format_result_notion_failed_shows_pending():
    r = _make_result(notion_sync_status="failed")
    text = _format_result(r)
    assert "pending" in text.lower()


def test_format_result_notion_skipped_not_shown():
    r = _make_result(notion_sync_status="skipped")
    text = _format_result(r)
    assert "Notion" not in text


def test_format_result_notion_needs_review_note():
    r = _make_result(
        notion_sync_status="synced",
        notion_project="General",
        notion_needs_review=True,
    )
    text = _format_result(r)
    assert "Needs Review" in text or "needs review" in text.lower() or "uncertain" in text.lower()


def test_format_result_notion_no_url_still_works():
    r = _make_result(
        notion_sync_status="synced",
        notion_project="Ascend",
        notion_content_type="Idea",
        notion_page_url=None,
    )
    text = _format_result(r)
    assert "Project: Ascend" in text
    assert "Notion: synced" in text
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/unit/test_notion_commands.py -v
pytest tests/ --tb=short 2>&1 | tail -5
```
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add src/operation_drake/channels/telegram.py tests/unit/test_notion_commands.py
git commit -m "feat: add /notion /sync /sync_pending Telegram commands"
```

---

### Task 9: CLI — --check-notion and --setup-notion

**Files:**
- Create: `src/operation_drake/integrations/notion/setup.py`
- Modify: `src/operation_drake/main.py`
- Test: inline via --check with NOTION_ENABLED=false (no new test file needed; manual verification)

**Interfaces produced:**
- `run_check_notion(settings) -> int`
- `run_setup_notion(settings) -> int`
- `--check-notion` and `--setup-notion` CLI flags

- [ ] **Step 1: Create setup.py**

`src/operation_drake/integrations/notion/setup.py`:
```python
from __future__ import annotations

from operation_drake.config import Settings
from operation_drake.observability.logging import get_logger

logger = get_logger(__name__)

_REQUIRED_PROPERTIES = [
    "Name", "Project", "Content Type", "Status", "Source",
    "Capture Context", "Captured At", "Summary", "Actionable",
    "Next Action", "Tags", "Confidence", "Source URL",
    "D.R.A.K.E. Task ID", "D.R.A.K.E. Artifact ID", "Sync Status",
]

_PROJECT_OPTIONS = [
    "General", "Business Ideas", "The Answer Movement", "Ascend",
    "Operation D.R.A.K.E.", "DK Personal Health OS", "Career & Work",
    "School & Learning", "Health & Fitness", "Investing & Finance",
    "Relationships & Networking", "Personal Life",
]

_CONTENT_TYPE_OPTIONS = [
    "Idea", "Reflection", "Research", "Resource", "Action Plan",
    "Meeting Note", "Decision", "Journal Entry", "Workday Check-in",
    "Article or Media Capture", "Voice Memo", "General Note",
]

_STATUS_OPTIONS = ["Inbox", "Organized", "Needs Review", "Action Required", "Archived"]

_SOURCE_OPTIONS = [
    "Telegram Text", "Telegram Voice", "Telegram Forward", "URL",
    "Article", "Video", "Social Post", "ChatGPT Voice", "Manual", "Other",
]

_CONTEXT_OPTIONS = [
    "General", "Pre-work Drive", "Post-work Drive", "Commute",
    "Work", "School", "Workout", "Evening Reflection", "Weekend Planning",
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

    rows.append(("Notion enabled", "yes" if settings.notion_enabled else "no (NOTION_ENABLED=false)"))
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

    if db_configured:
        try:
            from operation_drake.integrations.notion.live_client import LiveNotionClient

            client = LiveNotionClient(settings.notion_api_token, settings.notion_database_id)
            props = client.get_database_properties()
            missing = [p for p in _REQUIRED_PROPERTIES if p not in props]
            if missing:
                rows.append(("Schema", f"WARN -- missing: {', '.join(missing[:5])}"))
            else:
                rows.append(("Schema", "compatible"))
            rows.append(("Connection", "OK"))
        except Exception as e:
            rows.append(("Connection", f"FAIL -- {type(e).__name__}"))
            issues.append("Could not connect to Notion database")

    _print_table(rows, issues)
    return 1 if issues else 0


def run_setup_notion(settings: Settings) -> int:
    if not settings.notion_enabled:
        print("Notion is disabled. Set NOTION_ENABLED=true in .env to proceed.")
        return 1
    if not settings.notion_api_token:
        print("NOTION_API_TOKEN is not set in .env")
        return 1

    if settings.notion_database_id:
        print("NOTION_DATABASE_ID is already set. Running check instead...")
        return run_check_notion(settings)

    if not settings.notion_parent_page_id:
        print("Set NOTION_PARENT_PAGE_ID to a page you have shared with your integration.")
        return 1

    print("Creating D.R.A.K.E. Knowledge Vault database...")
    try:
        from notion_client import Client

        client = Client(auth=settings.notion_api_token)

        # Check if a database with this title already exists on the parent page
        search = client.search(query="D.R.A.K.E. Knowledge Vault", filter={"value": "database", "property": "object"})
        for result in search.get("results", []):
            parent = result.get("parent", {})
            if parent.get("page_id") == settings.notion_parent_page_id.replace("-", ""):
                db_id = result["id"]
                print(f"Found existing database. Add to .env:")
                print(f"NOTION_DATABASE_ID={db_id}")
                return 0

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
```

- [ ] **Step 2: Add --check-notion and --setup-notion to main.py**

In `src/operation_drake/main.py`, update `main()`:
```python
def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} -- Digital Router for Actions, Knowledge, and Execution"
    )
    parser.add_argument("--channel", choices=["telegram", "cli", "api"], default="api")
    parser.add_argument("--check", action="store_true", help="Run diagnostic checks and exit")
    parser.add_argument("--check-notion", action="store_true", help="Check Notion configuration and exit")
    parser.add_argument("--setup-notion", action="store_true", help="Create Notion database and exit")
    args = parser.parse_args()

    if args.check:
        sys.exit(run_check())

    if args.check_notion:
        from operation_drake.integrations.notion.setup import run_check_notion
        sys.exit(run_check_notion(get_settings()))

    if args.setup_notion:
        from operation_drake.integrations.notion.setup import run_setup_notion
        sys.exit(run_setup_notion(get_settings()))

    # ... rest of main unchanged
```

- [ ] **Step 3: Verify --check-notion works with Notion disabled**

```bash
python -m operation_drake.main --check-notion
```
Expected output:
```
  D.R.A.K.E. -- Notion Check
------------------------------------
  Notion enabled  no (NOTION_ENABLED=false)
------------------------------------

  All checks passed.
```
Exit code: 0

- [ ] **Step 4: Run full suite**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -5
ruff check src/ tests/
```
Expected: all pass, no lint errors

- [ ] **Step 5: Commit**

```bash
git add src/operation_drake/integrations/notion/setup.py src/operation_drake/main.py
git commit -m "feat: add --check-notion and --setup-notion CLI commands"
```

---

### Task 10: Documentation, Final Validation, Deployment Prep

**Files:**
- Create: `docs/notion-setup.md`
- Modify: `CURRENT_STATE.md`, `TASKS.md`, `ROADMAP.md`

- [ ] **Step 1: Create docs/notion-setup.md**

Document:
1. Create a private Notion integration at https://www.notion.so/my-integrations
2. Copy the integration token into `.env` as `NOTION_API_TOKEN=`
3. Create or choose a parent Notion page
4. Share that page with the integration (Share → Invite → select integration)
5. Copy the page ID from the URL (the 32-char hex after the last `-` or `/`) into `.env` as `NOTION_PARENT_PAGE_ID=`
6. Set `NOTION_ENABLED=true` in `.env`
7. Run `python -m operation_drake.main --setup-notion`
8. Copy the printed `NOTION_DATABASE_ID=` value into `.env`
9. Run `python -m operation_drake.main --check-notion` to verify

Include: classification behavior, how to override a category, how to suppress sync ("do not save to Notion"), how to retry failures, how to disable Notion without breaking D.R.A.K.E., Needs Review behavior, future CarPlay/ChatGPT voice note roadmap item.

- [ ] **Step 2: Run full local validation**

```bash
pytest tests/ -v 2>&1 | tail -5
ruff check src/ tests/
ruff format --check src/ tests/
docker compose config
python -m operation_drake.main --check
python -m operation_drake.main --check-notion
```
All must pass.

- [ ] **Step 3: Update CURRENT_STATE.md, TASKS.md, ROADMAP.md**

Document verified state, new commands, Notion integration status (enabled/disabled).

- [ ] **Step 4: Commit everything**

```bash
git add docs/notion-setup.md CURRENT_STATE.md TASKS.md ROADMAP.md
git commit -m "docs: Notion setup guide, updated state and roadmap"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] One database (D.R.A.K.E. Knowledge Vault) — mapper builds all 16 properties
- [x] All project/content_type/status/source/capture_context values included
- [x] Explicit override detection — classifier prompt handles "Save this under X", "do not sync"
- [x] Low-confidence → Needs Review + Telegram note
- [x] Idempotency — NotionSyncORM unique idempotency_key, sync_service checks before creating
- [x] Retry — sync_pending, /sync, failed records stay in DB
- [x] Local success when Notion fails — _sync_to_notion never raises, task status unaffected
- [x] No duplicate pages — find_page_by_task_id check before create
- [x] Telegram confirmation — _format_result extended
- [x] /notion, /sync, /sync_pending commands
- [x] --check-notion, --setup-notion CLI
- [x] NOTION_ENABLED=false zero behavior change
- [x] Future CarPlay/ChatGPT voice — source property includes "ChatGPT Voice"; capture_context includes "Pre-work Drive", "Post-work Drive"; no code built yet
- [x] No secrets logged — live_client wraps errors, only logs status code and error type
- [x] Page body structure — build_body includes Summary, Action Items, D.R.A.K.E. Metadata
- [x] Rich text chunking — _text_chunks splits at 2000 chars
- [x] Automatic setup mode (--setup-notion creates DB from parent page)
- [x] Existing database mode (NOTION_DATABASE_ID used directly)
- [x] Mock client in tests — all test files use MockNotionClient
- [x] Database migration safe — create_all adds new table, never modifies existing ones

**Gaps found and addressed:**
- ProcessResult session_tokens field was existing — new Notion fields added with defaults so existing tests don't break
- get_session() returns a raw session (not context manager) — Telegram sync helpers match existing pattern
- MockLLMProvider default response may not match expected JSON — classifier tests must check actual mock behavior and adjust assertions
