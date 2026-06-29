# TASKS.md

## Completed — Session 1 (2026-06-28)

- [x] Project scaffold: pyproject.toml, .gitignore, .env.example, directory tree
- [x] Config (pydantic-settings) and structured JSON logging
- [x] Pydantic schemas: InboundMessage, Attachment, IntentDecision, Task, Artifact, AgentRun
- [x] SQLAlchemy ORM models (all tables)
- [x] Storage layer: repositories for all entities, validated task transitions
- [x] LLM provider abstraction: base interface, mock, Anthropic, OpenAI
- [x] Transcription provider abstraction: base interface, mock, OpenAI Whisper
- [x] Ingestion: normalizer, URL detector, attachment handler
- [x] Content adapters: webpage, YouTube (blocked, URL preserved), audio
- [x] Project registry (JSON) and keyword classifier
- [x] Router agent with prompt template and JSON response parsing
- [x] Capture agent
- [x] Synthesis agent
- [x] Agent registry
- [x] Workflows: capture_note, summarize, extract_actions, create_research_brief, process_voice_note
- [x] Artifact service
- [x] Approval service
- [x] Orchestration service (full pipeline wiring)
- [x] CLI channel adapter (run_once + interactive)
- [x] Telegram channel adapter (text, voice, commands)
- [x] FastAPI app: /health, /tasks, /tasks/{id}
- [x] Prompt templates: router.md, capture.md, synthesis.md
- [x] Dockerfile, docker-compose.yml, Makefile
- [x] 41 tests (33 unit + 8 integration), all passing
- [x] Ruff lint clean
- [x] Docker Compose validates

## Next Milestone (Session 2)

Smallest sensible next step: **Live end-to-end test with real Telegram + real LLM.**

- [ ] Add Telegram bot token and Anthropic API key to `.env` on the VPS
- [ ] Deploy with `docker compose up -d`
- [ ] Verify `/start` and a real text message complete the pipeline
- [ ] Wire `/approve <id>` and `/reject <id>` Telegram commands to the task repository
- [ ] Test URL content extraction on a real public page
- [ ] Test voice note end-to-end with Whisper
