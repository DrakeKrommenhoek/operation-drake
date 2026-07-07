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

## Completed — Session 6 (2026-07-04)

- [x] Notion API v2025-09-03 compatibility: rewrite live_client.py with raw httpx + Notion-Version: 2022-06-28
- [x] Pin notion-client>=2.2,<3.0
- [x] --setup-notion: auto-repair missing properties on existing databases
- [x] D.R.A.K.E. Knowledge Vault created and connected in production
- [x] All 16 properties verified: types correct, schema compatible
- [x] Automated pipeline: all 6 scenarios (business idea, reflection, Answer Movement, Ascend, pre-work drive, post-work drive)
- [x] Override test: explicit project instruction honored ✓
- [x] Do-not-sync test: sync skipped, local completed ✓
- [x] Low confidence: Needs Review + review flag ✓
- [x] Failure test: local task completes even when Notion auth fails ✓
- [x] Retry: failed sync retried successfully ✓
- [x] Task-level idempotency: already_synced on second attempt, 0 duplicate pages ✓
- [x] Production backup: backup_20260704_202520.tar.gz (20K)
- [x] CURRENT_STATE.md updated with live Notion status

## Completed — Session 7 (2026-07-07)

- [x] Imported 7 planning specs from the Claude Project into `docs/planning/` (00-COMMAND-CENTER through 06-wellness-agent)
- [x] Reconciled divergence between the specs' v1.1-v4/06 model and the repo's Phase 1-8 `ROADMAP.md`
- [x] Decision: v1.1/v1.2/v2/v3/v4/06 naming adopted as primary; old Phase 1-8 retired to a mapping appendix
- [x] Decision: `/brief` is a distinct job type from the `research_brief` SAFE_INTENT; casual-capture auto-execute is unchanged — documented in `CLAUDE.md` and `ROADMAP.md`
- [x] `ROADMAP.md` rewritten around the v-numbered specs, stale CarPlay item struck (superseded by v4 Module B / Telegram voice)
- [x] Confirmed no code conflict exists today: `SAFE_INTENTS` in `services/approval.py` already implements the auto-capture side of v1.1; the write-back/dedupe/meta-noise-filter scope in `01-v1_1-close-the-loop.md` is unbuilt, not conflicting

## Pending — Session 7

- [ ] Send 6 live Telegram scenarios and verify Notion pages manually
- [ ] Send voice notes for S5 (pre-work) and S6 (post-work) to verify Whisper + Notion sync
- [ ] Run `/notion`, `/sync_pending`, `/status`, `/projects`, `/inbox`, `/cost` via Telegram
- [ ] Build social-media / URL capture workflow (see docs/superpowers/specs/2026-07-04-social-media-capture-design.md)
- [ ] Model selection: choose between gpt-4o-mini and gpt-4o per intent
- [ ] Start v1.1 Close the Loop build: SHA-256 dedupe, `/done /archive /action /project` write-back commands, meta-noise filter, stale check-in auto-archive
