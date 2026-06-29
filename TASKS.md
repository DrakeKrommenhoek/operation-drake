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

## Pending — Session 4 (Deployment)

- [ ] Build Docker image on VPS
- [ ] Start containers with `docker compose up -d`
- [ ] Verify health endpoint responds at `http://localhost:8000/health`
- [ ] Run `--check` inside container, confirm `openai` and not `mock`
- [ ] Confirm Telegram polling starts in logs
- [ ] Confirm SQLite database created in `/opt/operation-drake/data/database/`
- [ ] Test container restart: data and artifacts persist
- [ ] Live Telegram message validation (6 messages + voice note)
- [ ] Unauthorized-user test
- [ ] Validate and run `scripts/backup.sh`, `scripts/smoke_test.sh`, `scripts/deploy.sh`
- [ ] Update `docs/vps-deployment.md` with exact operational commands
- [ ] Confirm no secret values in logs
- [ ] Commit and push any documentation updates
