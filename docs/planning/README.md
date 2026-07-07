# Planning docs — imported from Claude Project

These 7 files are the D.R.A.K.E. roadmap/spec docs from the Claude Project
("Operation Drake" planning space), copied in on 2026-07-07 so Claude Code
has them locally instead of only living in a Claude Project's memory.

- `00-COMMAND-CENTER.md` — master reference, phase order, vault lanes
- `01-v1_1-close-the-loop.md` — dedupe, Telegram write-back commands, meta-noise filter
- `02-v1_2-sunday-review.md` — Sunday digest agent
- `03-v2-plan-confirm-execute.md` — research brief plan/approve/execute flow
- `04-v3-evaluators-study.md` — idea scorer + study guide engine
- `05-v4-external-data.md` — health/voice/stock modules (superseded, see below)
- `06-wellness-agent.md` — replaces v4 Module A; Fitbit Air + Google Health API decision

## ⚠️ Read before doing anything else: these docs and the repo have diverged

I compared these specs against the actual state of `operation-drake` (cloned
from GitHub on 2026-07-07, latest commit `4bb49b3`) and found the two were
clearly written as **separate visions** that were never reconciled:

### 1. Different execution models
- **These specs** describe an *auto-capture-then-triage* flow: the bot writes
  to Notion immediately, and you triage afterward via reply commands
  (`/done`, `/archive`, `/action`, `/project <name>`) — see `01-v1_1`.
- **The repo** (`CLAUDE.md`, `TASKS.md`) has already built a different,
  more cautious model: a *task queue with approve/reject/correct* — safe
  intents auto-execute, everything else waits for `/approve` or `/reject`
  before anything happens. This is Session 2 work, already live.

These are not the same thing, and code for one doesn't satisfy the other.

### 2. The repo is already ahead of v1.1 on some fronts, behind on others
Per `CURRENT_STATE.md` / `TASKS.md` (Session 5–6, 2026-07-04), already **live
in production**:
- Notion one-way sync (D.R.A.K.E. Knowledge Vault, 16 properties)
- LLM classification → project / content type / capture context
- Explicit override detection ("save under X", "do not sync")
- Low-confidence → Needs Review flag
- `/notion`, `/sync`, `/sync_pending`, `/status`, `/projects`, `/inbox`, `/cost`

Still **missing**, and actually specified in `01-v1_1-close-the-loop.md`:
- SHA-256 dedupe / idempotency on inbound messages
- `/done`, `/archive`, `/action`, `/project <name>` write-back commands
- CAPTURE vs QUESTION vs COMMAND meta-noise filter
- Auto-archive stale Workday Check-ins after 7 days

### 3. Roadmap naming doesn't line up
Repo's own `ROADMAP.md` uses **Phase 1–8** (Foundation → Monitoring), last
touched 2026-06-28-ish framing. These docs use **v1.1 → v4 / DK_0726**
naming with hard "one phase at a time, 14-day soak" gating. Repo's
`ROADMAP.md` even lists a "ChatGPT/CarPlay voice import" item that
`05-v4-external-data.md` Module B explicitly says to *abandon* in favor of
Telegram voice notes — i.e. the repo roadmap has a stale item these specs
already superseded.

### 4. Health module: repo hasn't caught up to the June decision
`06-wellness-agent.md` records the Fitbit Air decision and the Google
Health API (`health.googleapis.com/v4/`) as the real integration point,
explicitly **not** the legacy Fitbit Web API. Nothing in the repo
(`src/operation_drake/`, `ROADMAP.md`) reflects this yet — Phase 4 in
`ROADMAP.md` still just says "Fitness/health log agent," ungated.

## Suggested next step in Claude Code

Don't start writing v1.1/v2/v3 code against these specs as-is. First have
Claude Code do a reconciliation pass:
1. Read this file + all 7 specs + `CLAUDE.md`, `ROADMAP.md`, `TASKS.md`,
   `CURRENT_STATE.md`.
2. Produce one merged roadmap: decide whether the task-queue
   approve/reject model or the auto-capture/triage-command model is the
   one going forward (they can coexist per-intent, but that needs to be a
   decision, not a default).
3. Update `ROADMAP.md` to either adopt the v1.1–v4 phase naming or
   explicitly map Phase 1–8 onto it, and strike the stale CarPlay item.
4. Only then resume building against whichever spec is current.
