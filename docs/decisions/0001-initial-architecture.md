# ADR 0001: Initial Architecture Decisions

**Date:** 2026-06-28
**Status:** Accepted

## Context

Starting a personal AI agent OS from scratch. Needed to choose persistence, messaging transport, agent architecture, and provider strategy.

## Decisions

### SQLite for persistence

Chosen over PostgreSQL. This is a single-user personal system. SQLite eliminates a dependency, runs without a separate process, and is trivially backed up with a file copy. Migrate to PostgreSQL only if concurrency or scale becomes a real constraint.

### Telegram with long polling

Chosen over webhooks. Long polling requires no domain, no TLS certificate, and no inbound firewall rule. This is the correct choice for initial development. Switch to webhooks when deploying to a stable server with a domain.

### Single FastAPI process

All agents (Router, Capture, Synthesis) run in the same Python process. They are logically separated through interfaces and modules. This avoids premature microservice complexity while keeping the code modular enough to split later.

### Provider abstraction for LLM and transcription

`LLMProvider` and `TranscriptionProvider` are abstract base classes. This means swapping Anthropic for OpenAI, or adding a local model, requires changing only the provider factory — not any agent or workflow code. Mock providers allow the full pipeline to run in tests with zero API calls.

### Task lifecycle with validated transitions

Tasks move through: `received → normalizing → interpreting → awaiting_approval → approved → running → completed`. Transitions are validated against an explicit map. This prevents tasks from jumping to illegal states and makes the processing pipeline inspectable.

### Approval gate for external actions

Safe internal actions (summarize, save note, transcribe, extract actions) execute automatically. Anything with external side effects (send email, post publicly, create calendar events) requires explicit user approval. This is hardcoded conservatively for v1.

### No hidden chain-of-thought

Agent reasoning is stored only as `rationale_summary` — a concise, user-safe explanation. Full chain-of-thought is never stored. This keeps the database readable by the user and avoids storing potentially misleading intermediate reasoning.

### Untrusted content boundary

Forwarded messages, URL content, and audio transcripts are tagged as untrusted data. They are stored and processed, but the orchestration service never allows them to override system prompts or escape their data context.
