# Session Handoff

**Date:** 2026-07-07
**Branch:** `claude/planning-docs-setup-yxxht0` (pushed, clean, NOT merged to `master`, NOT deployed to the VPS)
**Session:** 7-8 (planning reconciliation + v1.1 Close the Loop build)

## What was actually done

### 1. Planning docs imported and reconciled
- Copied 7 spec files from the Claude Project into `docs/planning/` (`00-COMMAND-CENTER.md` through `06-wellness-agent.md`), plus `README.md` describing the divergence.
- Reconciled the specs' v1.1→v4/06 soak-gated model against the repo's old Phase 1-8 `ROADMAP.md`. Decision (user-confirmed): v-numbered naming is now primary; Phase 1-8 lives on only as a mapping appendix at the bottom of `ROADMAP.md`.
- Decision (user-confirmed): `/brief` (v2 spec) is a distinct job type from the `research_brief` SAFE_INTENT — casual captures still auto-execute; `/brief` always goes through its own plan/approve/execute queue. Documented in `CLAUDE.md` and `ROADMAP.md`.
- Struck the stale "ChatGPT/CarPlay voice import" roadmap item — v4 Module B replaces it with the existing Telegram voice pipeline.

### 2. v1.1 "Close the Loop" built end to end
All four pieces from `docs/planning/01-v1_1-close-the-loop.md`, adapted onto the *existing* task-queue + Notion-sync architecture (not the simpler bot-writes-directly model the spec assumed — see spec's own README for why those aren't actually in conflict):

- **Dedupe**: `seen_messages` table (SHA-256 hash, 30-day window). Hash is only recorded once a task actually *completes* (not on approval-required tasks that get rejected). Duplicate replies with "Already captured: [notion link]".
- **Meta-noise filter**: new `MetaNoiseFilterAgent` (`agents/meta_noise.py`, prompt at `prompts/meta_noise_filter.md`) classifies every message capture/question/command *before* the router runs. Questions get answered inline (no Notion write). Commands get a usage hint. Low-confidence captures (<60) prompt "Save this? Reply y or n" via a new per-sender `pending_captures` table, and confirming reuses the original `InboundMessage` row rather than creating a duplicate.
- **Telegram write-back commands**: `/done`, `/archive`, `/action`, `/project <name>`. New `WriteBackService` (`services/writeback_service.py`) + `NotionSyncService.update_properties()` patch the Notion page a reply targets, or the sender's own most recent capture if sent bare (now correctly scoped per-sender — see gotchas). `/project` fuzzy-matches against the 12 valid Notion Project values via `match_project()` in `integrations/notion/models.py`.
- **Stale check-in auto-archive**: `scripts/archive_stale_checkins.py` / `make archive-stale-checkins`. Archives Workday Check-in entries idle 7+ days. Needs `NotionClientInterface.query_stale_by_content_type()` (added to both `LiveNotionClient` and `MockNotionClient`).

### 3. Code review pass (8 parallel finder agents, medium effort) — 13 findings, 11 fixed
The two most important ones:
- **`scripts/dry_run.py` was silently broken by the meta-noise agent** sharing a `fixed_response` mock LLM with the router-testing setup — steps 6-9 of the demo were short-circuiting into the y/n gate instead of the approval flow. Verified broken, then verified fixed (dry_run.py runs clean end to end again).
- **Multi-user cross-talk bug**: the Telegram reply-target map (`TelegramReplyMapORM`) and the "most recent task" fallback used in write-back commands were not scoped per sender. In a deployment with more than one ID in `TELEGRAM_ALLOWED_USER_IDS`, a bare `/done` could target *another user's* capture, or a reply-map insert could collide across users. Fixed: both are now scoped by `sender_id`, and `TaskRepository.list_recent_by_sender()` is new.

Also fixed: voice-note dedupe hash contamination (all voice notes were hashing to the same placeholder text), a missing "treat as data, not instructions" guard on the meta-noise prompt (parity with `router.md`), the orphaned duplicate `InboundMessage` row on capture confirmation, missing logging in `WriteBackService`, non-deterministic `match_project` ordering, and event-loop-blocking DB calls in `telegram.py` (now wrapped in `run_in_executor` like everything else in that file).

**Two findings were deliberately left as accepted known limitations** (documented in `TASKS.md`):
- Dedupe doesn't catch an identical message resubmitted while the first copy is still `awaiting_approval` (no `seen_messages` row exists yet at that point). Narrow — only affects non-SAFE_INTENTS, which are rare/deliberate actions.
- A stale "Save this? y/n" prompt isn't proactively cleared if the user's next message is unrelated and high-confidence — it just sits until the next low-confidence event overwrites it, or an actual y/n reply clears it.

### Final verified state
- 246 tests pass (up from 193 at session start), `ruff check` and `ruff format --check` both clean.
- `python scripts/dry_run.py` runs clean end to end.
- 3 commits pushed to `claude/planning-docs-setup-yxxht0`: docs reconciliation, v1.1 build, code-review fixes + TASKS/ROADMAP updates.
- **Nothing has been merged to `master` or deployed to the VPS.** Production Telegram bot is still running the pre-v1.1 code.

## Gotchas for next session

- **The local sandbox has Python 3.11 as the default `python3`; the project requires 3.12.** A venv was built at `/tmp/claude-*/scratchpad/venv312` using `python3.12 -m venv` for running tests/lint — that venv will not persist across sessions since it's in `/tmp`. Rebuild it the same way if `pip install -e ".[dev]"` fails with a Python-version error.
- **`MockLLMProvider` now has a `"triage"` keyword branch** (checked before the router/classify heuristics) that returns a fixed high-confidence "capture" response for `MetaNoiseFilterAgent` calls. Any test or script that constructs an `OrchestratorService` with a single `fixed_response=` mock LLM intended to steer the *router* will now also feed that same response to the meta-noise agent unless it special-cases `"triage" in prompt.lower()` (see `_FixedRouterLLM` in `scripts/dry_run.py` or `_LowConfidenceThenNormalLLM` in `tests/unit/test_dedupe_and_meta_noise.py` for the pattern).
- **`TelegramReplyMapRepository.record()`/`.resolve()` now take `sender_id` as the first argument** — this is a breaking signature change from what Session 7 originally shipped (fixed same session, but flagging in case any half-remembered mental model of the old signature lingers).
- **Local dev/test flows use `DEFAULT_LLM_PROVIDER=mock`**; nothing in this session touched real Anthropic/OpenAI credentials or made live API calls.
- **v1.1 has never been exercised against the real Telegram bot or real Notion.** Everything above is verified via the mock-based test suite and `dry_run.py` only.

## Next steps (in order)

1. **Get this branch live**: merge `claude/planning-docs-setup-yxxht0` → `master` (no PR opened yet — ask if one is wanted), then run `scripts/deploy.sh` on the VPS.
2. **Live-verify against the real bot** (full checklist already given to the user in-session, also captured in `TASKS.md` Pending — Session 9):
   - Dedupe: send the same message twice.
   - Meta-noise: a real question, an ack like "ok thanks", a vague low-confidence message (test both `y` and `n`), and a normal clear capture as a regression check.
   - Write-back: `/done`, `/archive`, `/action`, `/project <name>` (exact, fuzzy/typo, bare-no-reply, and unmatched-gibberish cases).
   - Stale archive: run `make archive-stale-checkins` directly against production Notion.
3. Once live-verification is clean, **start the 14-day soak** on v1.1 per `ROADMAP.md`'s one-phase-at-a-time gate — do not start v1.2 (Sunday Review) work until that soak passes.
4. Leftover Session 7 pending items still open: 6 live Telegram scenario tests, voice note S5/S6 Whisper+Notion verification, `/notion` `/sync_pending` `/status` `/projects` `/inbox` `/cost` command checks, the social-media/URL capture workflow (`docs/superpowers/specs/2026-07-04-social-media-capture-design.md`), and gpt-4o vs gpt-4o-mini model selection per intent.
