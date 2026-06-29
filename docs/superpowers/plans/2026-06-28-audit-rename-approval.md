# Operation D.R.A.K.E. — Audit, Rename, and Approval Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rename the Python package to `operation_drake`, wire the full approval loop, add auth guard and diagnostic command, remove dead code, and produce a verified local dry-run with no VPS deployment.

**Architecture:** All changes are in-place edits to the existing single-service codebase. The rename is a directory move + mass import rewrite. The approval loop adds three methods to OrchestratorService and wires them into TelegramAdapter and CLIAdapter. No new agents, no new infrastructure.

**Tech Stack:** Python 3.12, FastAPI, SQLite, SQLAlchemy, Pydantic v2, python-telegram-bot, ruff, pytest

## Global Constraints

- No VPS deployment in this session
- No new agents or broadened scope
- `python -m operation_drake.main --channel cli` must work after rename
- All secrets masked in logs (token/key presence checked, value never logged)
- ruff check AND ruff format --check must both pass at end
- 41+ tests must pass (new tests required for approval loop and auth)

---

### Task 1: Package Rename

**Files:**
- Move: `src/personal_agent_os/` → `src/operation_drake/`
- Modify: `pyproject.toml` (name, find-packages path)
- Modify: all 53 `.py` files under `src/` and `tests/` (import rewrite)
- Modify: `Dockerfile`, `docker-compose.yml`, `Makefile`, `README.md`, `CLAUDE.md`

**Interfaces:**
- Produces: `operation_drake` importable package; `python -m operation_drake.main` works

### Task 2: Fix Formatting

**Files:** All `.py` files (26 need reformatting per ruff format --check)

### Task 3: Config + Auth Guard

**Files:**
- Modify: `src/operation_drake/config.py` — add `telegram_allowed_user_ids: str = ""`
- Modify: `src/operation_drake/channels/telegram.py` — auth guard on every handler
- Modify: `.env.example` — add `TELEGRAM_ALLOWED_USER_IDS=`

### Task 4: Approval Loop

**Files:**
- Modify: `src/operation_drake/services/orchestration.py` — add `execute_approved_task`, `reject_task`, `correct_task`
- Modify: `src/operation_drake/channels/telegram.py` — wire `/approve`, `/reject`, `/correct`, `/task`, `/status`
- Modify: `src/operation_drake/channels/cli.py` — add `approve`, `reject`, `correct` one-shot methods

### Task 5: Diagnostic Command

**Files:**
- Modify: `src/operation_drake/main.py` — add `--check` argument and `run_check()` function

### Task 6: Remove Dead Code

**Files:**
- Delete: `src/operation_drake/agents/registry.py`
- Delete: `src/operation_drake/ingestion/attachment_handler.py`

### Task 7: Tests

**Files:**
- Modify: `tests/integration/test_orchestration.py` — add approval loop tests
- Create: `tests/unit/test_auth.py` — auth guard tests
- Create: `tests/unit/test_check.py` — diagnostic check tests

### Task 8: Full Validation + Dry Run
