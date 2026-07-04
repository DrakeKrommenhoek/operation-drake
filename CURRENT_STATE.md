# CURRENT_STATE.md

Last updated: 2026-07-04 (Session 5 — Notion integration complete, pending live connection)

## Verified Facts

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
- Latest commit: `36d6411 feat: token cost tracking, /cost command, cost in approval messages`
- Git working tree: clean
- Local and remote are in sync

### Local Application Status
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
- Deployed commit: `36d6411` (matches local and GitHub)

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

## Next Session

Resume with:

```
Resume Operation D.R.A.K.E. Session 6.
First: connect Notion integration on the VPS (follow docs/notion-setup.md).
Run --check-notion inside the container to verify.
Then complete live Telegram tests: voice note, /status, /projects, /inbox, /cost, /notion.
Then build the second workflow: article/URL/video capture.
```
