# CURRENT_STATE.md

Last updated: 2026-06-28

## Verified Facts

### Local Environment
- Python 3.12.10
- Docker 29.2.1
- Docker Compose v5.0.2
- Git 2.52.0
- Operating system: Windows 11 (development machine)
- Target deployment: Ubuntu VPS (not yet accessed in this session)

### Repository Status
- Location: `C:\Users\drake\Desktop\operation-drake\`
- Git: not yet initialized (directory was empty at session start)
- All source files created in this session

### Application Status
- Package installs cleanly: `pip install -e ".[dev]"` ✓
- All imports resolve correctly ✓
- 41 tests pass (33 unit, 8 integration) ✓
- Ruff lint: all checks passed ✓
- Docker Compose: validates cleanly ✓
- Database: SQLite initializes correctly (verified in integration tests) ✓
- Health endpoint: implemented (not yet tested against running server)
- CLI pipeline: full end-to-end with mock providers verified ✓
- Telegram adapter: implemented, not tested (no token in this session)
- LLM providers: Anthropic and OpenAI implemented, not tested (no keys in this session)
- Transcription: OpenAI Whisper implemented, not tested (no key in this session)

### VPS Status
- **NOT VERIFIED** — SSH access was not checked in this session
- No deployment has been performed
- VPS deployment instructions exist in `docs/vps-deployment.md`

## Credentials Needed

| Credential | Variable | Status |
|---|---|---|
| Telegram bot token | `TELEGRAM_BOT_TOKEN` | Not configured |
| Anthropic API key | `ANTHROPIC_API_KEY` | Not configured |
| OpenAI API key | `OPENAI_API_KEY` | Not configured |
| Whisper API key | `OPENAI_WHISPER_API_KEY` | Not configured (falls back to OpenAI key) |

## What Was Built This Session

Complete foundation and first vertical slice:

- Full project scaffold (pyproject.toml, .env.example, .gitignore, directory tree)
- Pydantic v2 schemas for all core data contracts
- SQLAlchemy ORM models for all tables
- Storage repositories with validated task lifecycle transitions
- LLM provider abstraction (mock, Anthropic, OpenAI)
- Transcription provider abstraction (mock, OpenAI Whisper)
- Ingestion: normalizer, URL detector, attachment handler
- Content adapters: webpage (basic), YouTube (blocked/preserved), audio (blocked)
- Project registry (JSON) and keyword-based classifier
- Three agents: Router, Capture, Synthesis — each with prompt templates
- Five workflows: capture_note, summarize, extract_actions, create_research_brief, process_voice_note
- Orchestration service (full pipeline)
- CLI channel adapter (run_once + interactive)
- Telegram channel adapter (text, voice, 5 commands)
- FastAPI app with /health and /tasks endpoints
- Dockerfile, docker-compose.yml, Makefile
- Documentation: CLAUDE.md, README.md, ROADMAP.md, TASKS.md, ADR 0001, VPS guide

## Known Limitations

- Project classifier uses keyword matching only — no LLM fallback yet
- `/approve` and `/reject` Telegram commands are stubs (not fully wired to task repository)
- URL content extraction is basic (no JavaScript rendering, no paywall handling)
- YouTube videos: URL preserved, content not fetched
- Voice transcription not tested end-to-end (mock only)
- No conversation memory across messages yet
- No web search integration yet
- VPS not deployed or verified

## Next Milestone

Add Telegram bot token and Anthropic API key, deploy to VPS, and verify a real message completes the full pipeline end-to-end. Then wire `/approve` and `/reject` commands.
