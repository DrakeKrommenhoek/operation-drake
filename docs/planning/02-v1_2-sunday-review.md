# v1.2: Sunday Weekly Review Agent

Effort: 1 weekend. Prereq: v1.1 shipped and soaked 14 days.

## Goal

Every Sunday 7:00 PM MT, one Telegram digest that reviews the week and enforces the feedback loop. Highest value per line of code in the whole roadmap.

## Scope

### 1. Data pull (Notion API, no SQL needed)
- Query the Knowledge Vault data source for entries where Captured At >= last Monday.
- Also query all entries with Status = Inbox regardless of age (the rot report).

### 2. Digest composition (one Claude call)
Input: the week's entries as JSON. Output sections:
- **Captured this week** grouped by Project, one line each.
- **Moved forward**: entries that changed to Organized or Archived this week (diff against a weekly SQLite snapshot of statuses).
- **Rotting in Inbox**: anything older than 14 days still in Inbox, with age.
- **Top 3 next actions** ranked by leverage (Claude ranks using the entry Summary and Next Action fields).
- **One kill candidate**: the digest must name exactly one entry to archive or one idea to kill. Non-negotiable section.

### 3. Metrics (the feedback loop, computed not vibed)
Store weekly in SQLite table `weekly_metrics(week TEXT, pct_triaged REAL, actions_completed INT, improvement_shipped TEXT)`:
- pct_triaged = 1 - (Inbox count / total captures this week)
- actions_completed = entries moved to Organized this week
- improvement_shipped = free text, prompted: "What did you ship to the bot this week? Reply to log it."
Digest shows this week vs last week. "Never worse than yesterday" = these three numbers, weekly.

### 4. Delivery
- Cron: `0 19 * * 0` America/Denver.
- Single Telegram message, under 4096 chars; if longer, split at section boundaries.

## Out of scope
- Fitbit, voice memos, stock data (v4)
- Any interactive planning (v2)

## Done when
- Two consecutive Sundays arrive on time with zero manual intervention.
- The kill-candidate section has resulted in at least one real archive.

## Gotchas
- VPS timezone: set TZ explicitly in the cron environment, do not trust system default.
- Snapshot statuses every Sunday BEFORE composing, so next week's diff works.
- If Notion API fails, send the error to Telegram instead of failing silently.
