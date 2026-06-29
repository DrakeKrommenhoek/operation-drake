# Operation Drake — Roadmap

## Phase 1: Foundation and Universal Inbox ✓ (current)

**Exit criteria:**
- [x] Repository structure exists and builds cleanly
- [x] Health endpoint responds
- [x] SQLite initializes and persists tasks
- [x] CLI adapter completes the full pipeline with mock providers
- [x] Telegram adapter implemented (requires token to run live)
- [x] Voice transcription has real interface and mock implementation
- [x] Markdown artifacts created and queryable
- [x] All tests pass, lint clean, Docker Compose validates

## Phase 2: Reliable Interpretation and Approval

**Exit criteria:**
- [ ] `/approve <id>` and `/reject <id>` Telegram commands are fully wired
- [ ] Approval state persists across restarts
- [ ] LLM classification tested against real API (Anthropic + OpenAI)
- [ ] Confidence threshold tuned from real message data
- [ ] URL content extraction working for public pages
- [ ] YouTube video URL preserves link + prompts for transcript
- [ ] Voice transcription tested end-to-end with Whisper

## Phase 3: Project-Aware Memory and Context

**Exit criteria:**
- [ ] Project classifier uses LLM fallback when keyword matching fails
- [ ] Each project has a dedicated artifact storage path
- [ ] `/projects` command lists active projects
- [ ] Recent task context passed to agents for continuity
- [ ] Duplicate detection: similar notes within same project flagged

## Phase 4: Specialized Task Agents

**Exit criteria:**
- [ ] Research agent: searches web, synthesizes sources, cites claims
- [ ] PE research agent: deal analysis, LBO framing, industry memos
- [ ] Calendar/scheduling agent (requires explicit approval)
- [ ] Email drafting agent (requires explicit approval before sending)
- [ ] Fitness/health log agent for The Answer Movement

## Phase 5: External Tools and Actions

**Exit criteria:**
- [ ] Notion / Google Docs output (approval required)
- [ ] Google Calendar event creation (approval required)
- [ ] Email composition and send (approval required)
- [ ] Web search tool integrated into research workflows
- [ ] All external actions logged with full audit trail

## Phase 6: More Messaging Channels

**Exit criteria:**
- [ ] WhatsApp adapter (via Twilio or Meta API)
- [ ] Email ingestion adapter
- [ ] SMS ingestion adapter (Twilio)
- [ ] All channels share the same pipeline

## Phase 7: Proactive Routines and Scheduled Agents

**Exit criteria:**
- [ ] Daily digest: surface pending tasks, upcoming deadlines
- [ ] Weekly review: summarize what was captured, completed, deferred
- [ ] Scheduled research briefs (configurable cadence)
- [ ] Morning context push: calendar, tasks, priorities

## Phase 8: Monitoring, Evaluation, and Continuous Improvement

**Exit criteria:**
- [ ] LLM intent accuracy tracked over time
- [ ] Cost per message tracked and reported
- [ ] Agent run latency monitored
- [ ] Ability to correct past intent decisions and feed back into routing
- [ ] Regression test suite from real message history
