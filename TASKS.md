# TASKS.md

## Completed — Session 1 (2026-06-28)

- [x] Project scaffold, schemas, ORM models, repositories
- [x] LLM and transcription provider abstractions (mock, Anthropic, OpenAI)
- [x] Ingestion, content adapters, project registry, keyword classifier
- [x] Router, Capture, Synthesis agents with prompt templates
- [x] Five workflows: capture_note, summarize, extract_actions, research_brief, process_voice_note
- [x] Orchestration service (full pipeline)
- [x] CLI and Telegram channel adapters
- [x] FastAPI app with /health and /tasks endpoints
- [x] Dockerfile, docker-compose.yml, Makefile
- [x] 41 tests, ruff clean, Docker Compose validates

## Completed — Session 2 (2026-06-28)

- [x] Rename package `personal_agent_os` → `operation_drake`
- [x] ruff format applied to all files
- [x] `TELEGRAM_ALLOWED_USER_IDS` auth guard
- [x] Full approval loop: `execute_approved_task`, `reject_task`, `correct_task`
- [x] Telegram commands: `/approve`, `/reject`, `/correct`, `/task`, `/inbox`, `/projects`
- [x] `python -m operation_drake.main --check` diagnostic command
- [x] Dead code removed (agent registry, attachment handler)
- [x] FastAPI `on_event` deprecation fixed
- [x] 56 tests, ruff clean

## Completed — Session 3 (2026-06-29)

- [x] Root cause fixed: `_safe_text()` preserves all content (no character stripping)
- [x] `_split_message()` for Telegram's 4,096-character limit
- [x] Error handler registered on Telegram Application
- [x] `.env` duplicate key bug fixed (mock was overriding openai)
- [x] Provider factories raise `ValueError` on unknown names (no silent mock fallback)
- [x] `init_db()` auto-creates database directory
- [x] `docker-compose.yml`: port 8000 bound to `127.0.0.1` only
- [x] `Dockerfile`: non-root `drake` user (UID 1000)
- [x] 37 Telegram safety regression tests added
- [x] 95 tests total, ruff clean
- [x] VPS inspected: Ubuntu 24.04, Docker 29.6.1 installed, swap added
- [x] `drake` user added to `docker` group
- [x] Application directories created at `/opt/operation-drake/data/`
- [x] Repository cloned to `/opt/operation-drake/` at commit `75c21f8`
- [x] Production `.env` created with `600` permissions
- [x] All production secrets configured (not displayed or committed)
- [x] `DEFAULT_LLM_PROVIDER=openai`, `DEFAULT_TRANSCRIPTION_PROVIDER=openai_whisper` confirmed

## Completed — Session 4 (2026-07-04)

- [x] Dockerfile: `COPY src/ src/` added before pip install (fixes src-layout editable install)
- [x] `.dockerignore` created (excludes .env, data/, tests/, build artifacts)
- [x] Docker image built on VPS: `operation-drake-api:latest`, `operation-drake-telegram:latest`
- [x] Containers started: API (healthy), Telegram (polling)
- [x] Health endpoint verified: `{"status":"ok","database":"connected"}`
- [x] Production diagnostic: openai + openai_whisper, 1 authorized user, all checks passed
- [x] `docker-compose.yml`: telegram health check disabled (no HTTP server in polling mode)
- [x] Restart test: containers recover, database and backups persist
- [x] `scripts/deploy.sh`, `scripts/backup.sh`, `scripts/smoke_test.sh` created
- [x] Smoke test passed: 6/6 checks
- [x] First backup created: `backups/backup_20260704_172108.tar.gz`
- [x] Live Telegram test: `save_note` → intent routed, artifact saved, response returned
- [x] Live Telegram test: `summarize` → summary returned, artifact saved
- [x] Live Telegram test: ambiguous input → approval triggered (not guessed)
- [x] Bug fix: `extract_actions` summary now returns formatted checkbox list, not just count
- [x] Token cost tracking: `LLMResponse` counts threaded through agents → workflows → AgentRunORM
- [x] `/cost` Telegram command: total tokens + estimated USD spend
- [x] Approval messages include running session spend before confirmation
- [x] Auth guard verified: all 12 handler entry points check `_is_allowed`

## Completed — Session 5 (2026-07-04)

- [x] Notion integration: D.R.A.K.E. Knowledge Vault database schema (16 properties)
- [x] `NotionClassifier`: LLM-based classification → project, content_type, capture_context, confidence, sync_to_notion
- [x] `NotionPropertyMapper`: classification → Notion API property dict with chunking
- [x] `NotionBodyBuilder`: structured page body (Summary, Action Items, Metadata)
- [x] `NotionSyncService`: idempotency (notion:<task_id> key), retry, outbox tracking
- [x] `NotionSyncORM` / `NotionSyncRepository`: persistent sync state in SQLite
- [x] `LiveNotionClient`: real Notion API via `notion-client>=2.2`
- [x] `MockNotionClient`: configurable test double (auth/timeout/rate_limit failures)
- [x] Explicit override detection: "save under X", "do not sync", content type overrides
- [x] Low-confidence → Needs Review + Telegram note
- [x] Notion failure never changes task status, never loses local data
- [x] `ProcessResult` extended with notion_sync_status, notion_page_url, notion_project, notion_content_type, notion_needs_review
- [x] Telegram format extended with Project/Type/Notion synced summary
- [x] Telegram commands: `/notion`, `/sync <task_id>`, `/sync_pending`
- [x] CLI: `--check-notion`, `--setup-notion` (creates DB from parent page, idempotent)
- [x] `NOTION_ENABLED=false` default — zero behavior change to existing workflows
- [x] `docs/notion-setup.md`: complete Notion setup guide
- [x] 193 tests pass (98 new Notion-specific tests), ruff clean

## Pending — Session 6

- [ ] Live Notion test: connect integration on production, verify end-to-end sync
- [ ] Live voice note test (send short voice note, verify transcription + routing)
- [ ] Test `/notion`, `/sync_pending` commands on production
- [ ] Build second workflow: article/URL/video capture (extract from external content)
- [ ] Model selection: add ability to choose between gpt-4o-mini and gpt-4o per intent
