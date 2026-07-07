# v1.1: Close the Loop

Effort: 1 weekend. Prereq: existing Telegram-to-Notion bot running on VPS.

## Problem

The bot writes to Notion but never reads. It creates duplicates (there are already two Idempotency Test entries), turns questions to the bot into vault entries, and forces all triage into the Notion UI.

## Scope (build exactly this, nothing more)

### 1. Dedupe / idempotency
- SHA-256 hash of normalized message content (lowercase, strip whitespace).
- Store hash in SQLite table `seen_messages(hash TEXT PRIMARY KEY, notion_page_id TEXT, created_at TEXT)`.
- On match within 30 days: skip Notion write, reply "Already captured: [link]".

### 2. Telegram write-back commands
Reply to any bot capture confirmation with:
- `/done` sets Status = Organized
- `/archive` sets Status = Archived
- `/action` sets Status = Action Required, Actionable = true
- `/project <name>` sets Project (fuzzy match against the 12 project options)
- Store telegram_message_id to notion_page_id mapping in SQLite so replies resolve to pages.

### 3. Meta-noise filter
- Before creating a page, classify the message: CAPTURE vs QUESTION vs COMMAND (one cheap Claude call with the message text).
- QUESTION: answer in Telegram, do not write to Notion.
- Low-confidence captures (below 60): ask "Save this? y/n" instead of auto-writing.

### 4. Auto-archive stale check-ins
- Daily cron: any entry with Content Type = Workday Check-in and Captured At older than 7 days flips to Status = Archived.

## Out of scope
- Weekly digest (v1.2)
- Any new integrations
- Inline keyboard buttons (plain reply commands are fine here; buttons come in v2)

## Done when
- Full inbox triaged from Telegram without opening Notion once.
- Sending the same message twice produces one entry.
- Asking the bot a question produces zero vault entries.

## Gotchas
- Notion API rate limit is ~3 req/s; batch nothing, just sequential with small sleep.
- Telegram reply_to_message_id is how you resolve which capture a command targets. If the user sends a bare command with no reply, apply it to the most recent capture and confirm.
- Never log message content with secrets. Confirm branch before starting.
