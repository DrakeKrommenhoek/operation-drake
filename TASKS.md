# TASKS.md

## Completed — Session 1 (2026-06-28)

- [x] Project scaffold: pyproject.toml, .gitignore, .env.example, directory tree
- [x] Config (pydantic-settings) and structured JSON logging
- [x] Pydantic schemas: InboundMessage, Attachment, IntentDecision, Task, Artifact, AgentRun
- [x] SQLAlchemy ORM models (all tables)
- [x] Storage layer: repositories for all entities, validated task transitions
- [x] LLM provider abstraction: base interface, mock, Anthropic, OpenAI
- [x] Transcription provider abstraction: base interface, mock, OpenAI Whisper
- [x] Ingestion: normalizer, URL detector
- [x] Content adapters: webpage, YouTube (blocked, URL preserved), audio
- [x] Project registry (JSON) and keyword classifier
- [x] Router agent with prompt template and JSON response parsing
- [x] Capture agent, Synthesis agent
- [x] Workflows: capture_note, summarize, extract_actions, create_research_brief, process_voice_note
- [x] Artifact service, Approval service
- [x] Orchestration service (full pipeline wiring)
- [x] CLI channel adapter (run_once + interactive)
- [x] Telegram channel adapter (text, voice)
- [x] FastAPI app: /health, /tasks, /tasks/{id}
- [x] Prompt templates: router.md, capture.md, synthesis.md
- [x] Dockerfile, docker-compose.yml, Makefile
- [x] 41 tests (33 unit + 8 integration), all passing
- [x] Ruff lint clean, Docker Compose validates

## Completed — Session 2 (2026-06-28)

- [x] Rename package: `personal_agent_os` → `operation_drake` (all files, imports, docs, config)
- [x] ruff format applied to all 26 files needing it
- [x] `TELEGRAM_ALLOWED_USER_IDS` — config, `.env.example`, auth guard in all Telegram handlers
- [x] Approval loop: `execute_approved_task`, `reject_task`, `correct_task` on orchestrator
- [x] Telegram commands: `/approve`, `/reject`, `/correct`, `/task`, `/inbox`, `/projects`, `/status`
- [x] CLI adapter: `approve()`, `reject()`, `correct()` methods
- [x] `python -m operation_drake.main --check` diagnostic command
- [x] Dead code removed: `agents/registry.py`, `ingestion/attachment_handler.py`
- [x] FastAPI `on_event` deprecation fixed with lifespan
- [x] pytest-asyncio loop scope warning silenced
- [x] `scripts/dry_run.py` — complete 10-step mock pipeline validation
- [x] 56 tests pass (33 unit + 23 integration), zero warnings
- [x] Ruff check clean, format clean, Docker Compose validates, --check passes

## Next Milestone (Session 3)

**Objective: First live end-to-end test with real credentials.**

- [ ] Set `TELEGRAM_BOT_TOKEN` in `.env`
- [ ] Set `TELEGRAM_ALLOWED_USER_IDS` to your Telegram user ID
- [ ] Set `ANTHROPIC_API_KEY` and `DEFAULT_LLM_PROVIDER=anthropic` in `.env`
- [ ] Run `python -m operation_drake.main --check` — verify all green
- [ ] Run `python -m operation_drake.main --channel telegram`
- [ ] Send a text message — verify intent classification uses real Claude
- [ ] Send a voice note — verify Whisper transcription (if `OPENAI_WHISPER_API_KEY` set)
- [ ] Send a URL — verify extraction and capture
- [ ] Test `/approve`, `/reject`, `/correct` commands live
- [ ] Verify artifact files created correctly
- [ ] Deploy to VPS via Docker Compose (see docs/vps-deployment.md)
