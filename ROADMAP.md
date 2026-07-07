# Operation Drake — Roadmap

Roadmap now follows the v1.1 -> v1.2 -> v2 -> v3 -> v4/06 phase specs in
`docs/planning/` (each spec file is the source of truth for scope and exit
criteria). This file tracks status against those specs. Hard rule carried
over from the specs: one phase at a time, 14-day soak before the next.

Reconciled against the old Phase 1-8 structure on 2026-07-07 — see the
mapping appendix at the bottom. Phase 1-8 language is retired; use
v1.1/v1.2/v2/v3/v4/06 naming going forward.

## Legend
- `[x]` done and verified
- `[~]` partially done / in progress
- `[ ]` not started

## Carried-over foundation work (predates v-numbering, still open)

From the old Phase 2 exit criteria — no spec file owns these, do before or
alongside v1.1:
- [ ] Confidence threshold tuned from real message data
- [ ] URL content extraction working for public pages
- [ ] YouTube video URL preserves link + prompts for transcript
- [ ] Voice transcription tested end-to-end with Whisper (live, not mock)

## v1.1: Close the Loop — IN PROGRESS

Spec: `docs/planning/01-v1_1-close-the-loop.md` | Gate: ships, then 14-day soak

Already shipped (Session 5-6 Notion work landed ahead of this spec):
- [x] Notion one-way sync, LLM classification -> project / content type / capture context
- [x] Explicit override detection, Needs Review flagging on low confidence

Spec scope still open:
- [ ] SHA-256 dedupe / idempotency (`seen_messages` table)
- [ ] `/done`, `/archive`, `/action`, `/project <name>` Telegram write-back commands
- [ ] CAPTURE vs QUESTION vs COMMAND meta-noise filter
- [ ] Auto-archive stale Workday Check-ins after 7 days

## v1.2: Sunday Weekly Review — NOT STARTED

Spec: `docs/planning/02-v1_2-sunday-review.md`
Gate: prereq v1.1 shipped + 14-day soak; done when 2 clean Sundays land on time

## v2: Plan -> Confirm -> Execute — NOT STARTED

Spec: `docs/planning/03-v2-plan-confirm-execute.md`
Gate: prereq v1.2 passes its two-Sunday gate; done when 5 briefs complete with zero manual intervention

**Reconciliation note (2026-07-07):** `research_brief` is a `SAFE_INTENT`
(auto-executes today per `services/approval.py` and `CLAUDE.md`). `/brief`
is a **distinct job type**, not a reclassification of that intent — casual
captures that classify as `research_brief` keep auto-executing unchanged.
The explicit `/brief <topic>` command always goes through the
plan/approve/execute queue described in this spec, regardless of
`SAFE_INTENTS`. See `docs/planning/README.md` for the divergence this
resolves.

## v3: Evaluators + Study Engine — NOT STARTED

Spec: `docs/planning/04-v3-evaluators-study.md`
Gate: prereq v2 passes its 5-brief gate; done when every Business Ideas entry is scored and one study cycle completes

**Naming note:** "Evaluators" here means the idea-scoring rubric (Module
A) — unrelated to the LLM-accuracy / observability work listed under
"Unphased backlog" below. Same word, different things; do not conflate
when reading old notes.

## v4: External Data — BLOCKED / PARTIAL

Spec: `docs/planning/05-v4-external-data.md`
Gate: prereq v1-v3 running clean a full month

- **Module A (Health): superseded** by `docs/planning/06-wellness-agent.md` — see below
- [ ] Module B: Voice Reflections (Telegram voice notes -> themes in Sunday digest)
- [ ] Module C: Stock Research (compliance-gated watchlist digest section)

**Stale item struck:** "ChatGPT / CarPlay voice import" (previously listed
under the old Phase 5 Notion Roadmap Items). Module B explicitly abandons
that path in favor of the existing Telegram Voice pipeline — there is no
CarPlay conversation-export API worth building against.

## 06: Wellness Agent (DK_0726 integration) — BLOCKED

Spec: `docs/planning/06-wellness-agent.md` | Replaces v4 Module A.

Gate: v1.1 shipped (Telegram write-back is the food/supplement logging
surface) AND DK_0726 Phase 0 complete (14 consecutive days of manual
logging). Hardware decided: Fitbit Air, ingested via the Google Health API
(`health.googleapis.com/v4/`) — explicitly **not** the legacy Fitbit Web
API, which shuts down September 2026.

## Unphased / ongoing backlog

Work that doesn't fit the v-numbered soak-gated sequence. Pick up
opportunistically — it neither blocks nor is blocked by the phase gates
above.

- [ ] WhatsApp / email / SMS channel adapters (old Phase 6)
- [ ] Google Calendar event creation, email compose + send (approval required either way)
- [ ] Monitoring & evaluation: LLM intent accuracy over time, cost-per-message
      breakdown, model selection per intent, agent run latency, regression
      suite from real message history (old Phase 8 — renamed here to avoid
      clashing with v3's "Evaluators")
- [x] Token cost tracked per agent run, `/cost` command (old Phase 8, already shipped)

## Appendix: mapping from the old Phase 1-8 structure (retired)

| Old phase | Status | Folded into |
|---|---|---|
| Phase 1: Foundation | done | n/a (bootstrap, no v-number owns it) |
| Phase 2: Interpretation and Approval | mostly done | approve/reject queue shipped; leftovers -> "Carried-over foundation work" above |
| Phase 3: Project-Aware Memory | not started | no v-number owns this yet; revisit after v1-v3 soak |
| Phase 4: Specialized Task Agents | not started | Fitness/health item -> `06-wellness-agent.md`; research/PE/calendar/email agents unphased, revisit after v2 |
| Phase 5: External Tools and Actions | mostly done | Notion sync shipped; bidirectional status sync + duplicate detection -> v1.1; CarPlay item struck (see v4 Module B) |
| Phase 6: More Messaging Channels | not started | Unphased backlog |
| Phase 7: Proactive Routines | partial | Weekly review -> v1.2; scheduled research briefs -> v2 |
| Phase 8: Monitoring and Evaluation | partial | Unphased backlog (renamed to avoid clash with v3 "Evaluators") |

Phase 1-8 language is retired as of this reconciliation (2026-07-07). Use
v1.1 / v1.2 / v2 / v3 / v4 / 06 naming going forward; this table exists only
so old references resolve.
