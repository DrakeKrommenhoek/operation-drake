# CURRENT_STATE.md

Last updated: 2026-07-13 (Session 9 — intake bot fixes merged to master; VPS not yet redeployed)

## Verified Facts — Session 9 (2026-07-13, checked from a sandboxed cloud session, no VPS access)

- PR #1 (`claude/telegram-intake-bot-fixes-2c7rct`) merged to `master` at `1c748a7`: source URL detection (`ingestion/url_detector.py`), Source/Source URL decoupling, deterministic `actionable` flag, meta-noise keyword pre-filter (with reviewed/hardened regex — see PR body for the five false-positive fixes)
- `master` HEAD verified locally (fresh `python3.12 -m venv` + `pip install -e ".[dev]"`): **280 tests pass**, `ruff check src/ tests/` clean
- Schema change not yet applied anywhere outside test SQLite: `pending_captures.entities` (new column) and `meta_noise_log` (new table) are created via `Base.metadata.create_all()` — no migration tooling in this repo
- **VPS status below (Session 6, commit `4bb49b3`) is stale** — the box has not been redeployed since. This session had no SSH/network path to the VPS to verify or update it. Deploy steps (backup `drake.db`, foreground dry-run, `docker compose up -d`/systemd, live Telegram smoke test) are tracked as pending in `TASKS.md` under "Session 10" and need to be run from a session/terminal with VPS access.

## Verified Facts (as of Session 6, 2026-07-04 — see note above)

### Local Environment
- Python 3.12.10
- Docker 29.2.1
- Docker Compose v5.0.2
- Git 2.52.0
- OS: Windows 11 (development machine)

### Repository Status
- Location (local): `C:\Users\drake\Desktop\operation-drake\`
- GitHub: `https://github.com/DrakeKrommenhoek/operation-drake.git`
- Branch: `master`
- Latest commit: `4bb49b3 fix: use raw httpx with Notion-Version 2022-06-28 in live_client` (superseded — see Session 9 note above; `master` is now at `1c748a7`)
- Git working tree: clean
- Local and remote are in sync

### Local Application Status (Session 6 snapshot)
- **193 tests pass**, zero failures, zero warnings (98 new Notion-specific tests)
- `ruff check`: all checks passed
- `ruff format --check`: all files formatted
- `docker compose config`: validates cleanly
- `python -m operation_drake.main --check`: all checks passed (openai, openai_whisper)
- `python -m operation_drake.main --check-notion`: passes (Notion disabled by default)

### VPS Status (DigitalOcean, Ubuntu 24.04 LTS)

**Verified:**
- Hostname: `drake`, accessible via `ssh drake-vps`
- Ubuntu 24.04 (kernel 6.8.0-124)
- 67 GB disk (3.9 GB used), 1.9 GB RAM + 1 GB swap
- Docker 29.6.1 and Docker Compose v5.2.0 installed
- User `drake` (UID 1000) exists and is in the `docker` group
- No conflicting applications or failed services

**Repository on VPS:**
- Location: `/opt/operation-drake/`
- Owner: `drake:drake`, permissions `750`
- Deployed commit: `4bb49b3` (matches local and GitHub)

**Persistent data directories (created, owned by drake:drake):**
- `/opt/operation-drake/data/database/`
- `/opt/operation-drake/data/artifacts/`
- `/opt/operation-drake/data/inbox/`
- `/opt/operation-drake/backups/`

**Production `.env`:**
- Location: `/opt/operation-drake/.env`
- Owner: `drake:drake`, permissions `600`
- `TELEGRAM_BOT_TOKEN` — SET
- `TELEGRAM_ALLOWED_USER_IDS` — SET (1 authorized user)
- `OPENAI_API_KEY` — SET
- `OPENAI_WHISPER_API_KEY` — SET
- `DEFAULT_LLM_PROVIDER=openai` — SET
- `DEFAULT_TRANSCRIPTION_PROVIDER=openai_whisper` — SET
- `NOTION_ENABLED=true` — SET
- `NOTION_API_TOKEN` — SET (never displayed or committed)
- `NOTION_PARENT_PAGE_ID` — SET (never displayed or committed)
- `NOTION_DATABASE_ID` — SET (D.R.A.K.E. Knowledge Vault)
- `NOTION_SYNC_MODE=automatic` — SET
- `NOTION_LOW_CONFIDENCE_THRESHOLD=0.70` — SET
- Secret values were never displayed, logged, or committed

**Containers (production, running):**
- `operation-drake-api-1`: Up, healthy, port `127.0.0.1:8000` only
- `operation-drake-telegram-1`: Up, health check disabled (polling bot, no HTTP server)
- Restart policy: `unless-stopped`
- Health endpoint: `{"status":"ok","database":"connected","service":"operation-drake","version":"0.1.0"}`

**Production diagnostic (inside container):** All checks passed — LLM: openai, Transcription: openai_whisper, 1 authorized user.

**Persistence verified:** Restart test passed — bot reconnects, database and backups survive.

## First Workflow: Telegram Intake and Response

The full pipeline is production-ready:

```
Telegram text/voice → normalization → LLM routing → workflow execution
→ artifact saved → InboundMessage + IntentDecision + Task + AgentRun + Artifact persisted
→ result sent to Drake's private Telegram chat
```

**Live tests completed (partial — extract_actions bug found and fixed mid-session):**
- `save_note`: authorized user accepted, intent routed, artifact saved, response returned
- `summarize`: summary text returned, artifact saved
- `extract_actions`: FIX DEPLOYED — now returns formatted checkbox list, not just count
- Ambiguous/unknown: triggers approval instead of guessing

**Pending live tests (send after deployment):**
- Voice note transcription end-to-end
- `/status`, `/projects`, `/inbox` commands
- `/cost` command

## Operational Scripts

| Script | Purpose |
|--------|---------|
| `scripts/deploy.sh` | git pull, docker compose build + up, health check |
| `scripts/backup.sh` | tar database + artifacts to `backups/` with timestamp |
| `scripts/smoke_test.sh` | health endpoint, diagnostic, dir checks (6/6 PASS) |

First backup created: `backups/backup_20260704_172108.tar.gz`

## Session 4 Changes

- Dockerfile: added `COPY src/ src/` before pip install (fixes src-layout build error)
- `.dockerignore`: created — excludes `.env`, `data/`, `tests/`, build artifacts
- `docker-compose.yml`: telegram service health check disabled (polling bot has no HTTP server)
- `scripts/deploy.sh`, `scripts/backup.sh`, `scripts/smoke_test.sh`: created
- `extract_actions` bug fixed: `WorkflowResult.summary` now contains the formatted checkbox list
- Token cost tracking: `input_tokens`/`output_tokens` threaded from `LLMResponse` through agent results and `WorkflowResult` to `AgentRunORM.token_count`
- `/cost` Telegram command: shows total tracked tokens and estimated spend (~$USD at gpt-4o-mini blended rate)
- Approval messages now include running session spend before asking for confirmation
- Model selection options: added to roadmap for a future session

## Session 5 Changes

### Notion Integration
- `src/operation_drake/integrations/notion/` package created:
  - `errors.py`, `models.py`, `client.py`, `mock_client.py`, `live_client.py`
  - `classifier.py` (LLM-based classification), `mapper.py`, `body_builder.py`
  - `sync_service.py` (idempotency, retry, outbox), `setup.py` (CLI commands)
- `NotionSyncORM` table added to database (safe additive migration via `create_all`)
- `NotionSyncRepository` with full CRUD and status tracking
- `notion-client>=2.2` added to dependencies
- Six new `.env` settings: `NOTION_ENABLED`, `NOTION_API_TOKEN`, `NOTION_PARENT_PAGE_ID`, `NOTION_DATABASE_ID`, `NOTION_SYNC_MODE`, `NOTION_LOW_CONFIDENCE_THRESHOLD`
- `ProcessResult` extended with Notion sync fields
- Telegram format shows Project / Type / Notion: synced after workflow completion
- Telegram commands: `/notion`, `/sync <task_id>`, `/sync_pending`
- CLI: `--check-notion`, `--setup-notion`
- `docs/notion-setup.md` created
- `prompts/notion_classifier.md` created

### Notion Status
- `NOTION_ENABLED=false` (default) — no behavior change to production bot
- Integration is ready to connect: follow `docs/notion-setup.md` to enable
- Production deployment with Notion requires: backup → set .env → deploy → `--check-notion` → live test

## Session 6 Changes

### Notion API Compatibility Fixes
- Notion API version `2025-09-03` (used by notion-client 3.x) broke `databases.create` schema and `databases.retrieve properties`
- `live_client.py`: rewritten to use raw `httpx` with pinned `Notion-Version: 2022-06-28` header — removes SDK version dependency entirely
- `pyproject.toml`: pinned `notion-client>=2.2,<3.0`
- `setup.py`: added `_apply_schema_to_existing()` using raw httpx for schema repair; `--setup-notion` auto-repairs missing properties on existing databases; `run_check_notion` returns exit code 2 for repairable schema warnings

### Notion Production Setup (Completed)
- D.R.A.K.E. Knowledge Vault created in Notion: 16 properties verified
- `NOTION_ENABLED=true` in production `.env`
- `--check-notion`: Schema compatible, Connection OK
- `--setup-notion`: Self-repairing — finds existing DB and applies missing schema

### Automated Pipeline Verification (All passed)
- S1: Business idea → Business Ideas / Idea ✓
- S2: Personal reflection → Personal Life / Reflection ✓
- S3: Answer Movement idea → The Answer Movement / Idea ✓
- S4: Ascend idea → Ascend / Action Plan ✓
- S5: Pre-work drive text → Career & Work / Workday Check-in / Capture Context: Pre-work Drive ✓
- S6: Post-work drive text → Career & Work / Reflection ✓
- Override test: "Save under Answer Movement" → The Answer Movement ✓
- Do-not-sync test: "Do not save to Notion" → sync skipped, local completed ✓
- Low confidence: → General / Needs Review / review=True ✓
- Auth failure test: local task completed even when Notion auth fails ✓
- Retry test: failed sync retried and succeeded ✓
- Task-level idempotency: second sync of same task → already_synced, 0 duplicate pages ✓
- `sync_pending`: 0 pending, 0 failed ✓

### Remaining Live Telegram Tests (need manual send)
- Send each of the 6 scenarios via Telegram to verify bot response format
- Send voice notes (S5 and S6) to verify Whisper transcription + Notion sync
- Run `/notion`, `/sync_pending`, `/status`, `/projects`, `/inbox`, `/cost` in Telegram

### Backups
- Pre-session: `backup_20260704_185516.tar.gz` (5.7K)
- Post-session: `backup_20260704_202520.tar.gz` (20K, includes test artifacts)

## Next Session

Resume with:

```
Resume Operation D.R.A.K.E. Session 7.
Notion is live in production. Start by sending the 6 live Telegram test scenarios
and verifying Notion pages. Then build the social-media / URL capture workflow
per docs/superpowers/specs/2026-07-04-social-media-capture-design.md.
```
