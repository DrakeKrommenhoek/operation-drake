# D.R.A.K.E. Command Center

Master reference for evolving the Telegram-to-Notion capture bot into a personal assistant.
Notion source of truth: https://app.notion.com/p/396408279f40813ca532fe65a58e02bf
Created: 2026-07-06. Review every Sunday.

## Stack (locked)

- VPS + Python + cron + SQLite state
- Telegram = the only UI
- Notion = the only store
- One Claude API call per job
- NO agent frameworks, NO orchestration platforms, NO vector DBs until something breaks

## Phase order and gating

| Phase | Spec file | Effort | Gate |
|-------|-----------|--------|------|
| v1.1 Close the Loop | 01-v1.1-close-the-loop.md | 1 weekend | ships, then 14-day soak |
| v1.2 Sunday Review | 02-v1.2-sunday-review.md | 1 weekend | 2 clean Sundays |
| v2 Plan-Confirm-Execute | 03-v2-plan-confirm-execute.md | 2-3 weekends | 5 briefs, zero manual intervention |
| v3 Evaluators + Study | 04-v3-evaluators-study.md | 2 weekends | all ideas scored, 1 study cycle done |
| v4 External Data | 05-v4-external-data.md | TBD | only after v1-v3 run clean |

Hard rule: ONE phase at a time. New feature ideas go into the vault and wait for Sunday.

## Vault lanes (28 entries organized)

- Business Ideas: Massage Parlor (top leverage), AI-for-small-PE (compliance gated), Protein Shake (kill candidate), WaaS pricing (reference)
- Career and Work: Scholarship Automation (v2 pilot task), PE Deal Flow Q3 2026 (interview prep)
- Ascend: Weekly Recruiting Review, Idempotency Test, TikTok reference
- The Answer Movement: Grounding, Pre-Practice Check-In, Serenity partnership, TMS (all parked for relaunch)
- Learning: Reactants Theory (v3 study pilot), Guitar
- Personal Life: challenge, habits, recipe, restaurant, reel, check-ins

## Cleanup queue (pending confirmation)

Archive: Idempotency duplicate, "New page", Clarification Request, Inquiry About Viewing Artifacts, Potentially Useful Content for Later Reference.

## Operating rules

1. One phase at a time; 14-day soak before the next.
2. Every Sunday digest names one thing to kill or archive.
3. Compliance hard-coded: no trade execution, no Mountaingate work product, pre-clearance before any personal trade.
4. No secrets or real health data in the repo. PowerShell only, no `&&` chaining. Confirm working directory and Git branch before touching files.
5. Session end: fill out .claude/commands/handoff.md with date, branch, what was actually done, gotchas.
