# v2: Plan -> Confirm -> Execute

Effort: 2-3 weekends. Prereq: v1.2 passed its two-Sunday gate.

## Goal

The "works while I work" behavior, scoped to exactly ONE task type: research briefs. You send a request from your desk, the assistant plans, you approve from your phone, it executes and delivers to Notion.

## Flow

1. User texts: `/brief scholarship automation landscape for CO students`
2. Bot drafts a plan (one Claude call): objective, 3-5 research questions, sources to hit, output format, estimated length.
3. Bot sends the plan with Telegram inline keyboard: **Approve** | **Edit** | **Cancel**.
4. Edit: user replies with changes, bot revises plan, re-sends buttons (max 3 revision rounds, then cancel).
5. Approve: job enters SQLite queue `jobs(id, type, plan_json, status, created_at, completed_at)`. Worker picks it up.
6. Worker executes: Claude API with web search tool, composes the brief.
7. Brief written to the vault as a new page: Content Type = Research, Status = Needs Review, full brief as page body, Summary property filled.
8. Confirmation to Telegram: "Brief done: [Notion link]. 3 key findings: ..."

## Architecture

- Same VPS, same bot process for steps 1-5.
- Separate worker process (systemd service or a second cron-polled script) for steps 6-8, so the bot stays responsive during long jobs.
- Job states: PENDING -> RUNNING -> DONE / FAILED. Failures ping Telegram with the error and stay retryable via `/retry <job_id>`.

## Pilot task

The Scholarship Automation entry. First real job: "Research brief: scholarship databases and application automation approaches for a CO undergrad, Economics major." Its output becomes the actual build plan for that project.

## Out of scope
- Any task type other than research briefs. No code-writing jobs, no emails, no multi-step agents. One verb.
- Autonomous execution without approval. Every job requires the button tap.

## Done when
- 5 briefs completed end to end with zero SSH sessions into the VPS.
- Median request-to-delivery under 30 minutes.

## Gotchas
- Telegram callback_query data is limited to 64 bytes; put the job id in it, not the plan.
- Timeout long Claude calls at 10 min and mark FAILED rather than hanging the worker.
- Store the plan verbatim in the finished Notion page so output can be audited against what was approved.
