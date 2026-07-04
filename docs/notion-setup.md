# Notion Integration Setup

## Overview

D.R.A.K.E. syncs completed outputs to a single Notion database called **D.R.A.K.E. Knowledge Vault**. Every captured note, voice memo, research brief, or action list gets classified and organized using Notion properties and filtered views.

Notion is a destination and review surface. The local SQLite database and artifact files remain the durable source of truth. A Notion failure never prevents local completion.

---

## First-time Setup

### Step 1: Create a Notion integration

1. Go to <https://www.notion.so/my-integrations>
2. Click **New integration**
3. Give it a name (e.g., `D.R.A.K.E.`)
4. Select the workspace where your pages live
5. Under Capabilities, enable **Read content**, **Update content**, **Insert content**
6. Click **Save**
7. Copy the **Internal Integration Token** (starts with `secret_`)

Do not share this token. Do not paste it into this chat.

### Step 2: Share a parent page with the integration

1. Open or create a Notion page where the database will live (e.g., `D.R.A.K.E. System`)
2. Click **Share** in the top-right corner
3. Click **Invite** → search for your integration by name → click **Invite**

The integration must have access to the parent page before the database can be created.

### Step 3: Get the parent page ID

The page ID is the 32-character hex string in the page's URL:
```
https://www.notion.so/My-Page-Title-abc123def456...
                                     ^^^^^^^^^^^^^^^  ← this is the page ID
```

Or the full URL path after the workspace slug.

### Step 4: Configure .env

Add to your `.env` file on the server:
```
NOTION_ENABLED=true
NOTION_API_TOKEN=secret_your_token_here
NOTION_PARENT_PAGE_ID=abc123def456...
```

Leave `NOTION_DATABASE_ID` empty for now.

### Step 5: Create the database

```bash
python -m operation_drake.main --setup-notion
```

If a D.R.A.K.E. Knowledge Vault database already exists on the parent page, the command finds it. Otherwise it creates one with the full property schema.

The command prints:
```
NOTION_DATABASE_ID=<id>
```

Copy that value into `.env`:
```
NOTION_DATABASE_ID=<id>
```

### Step 6: Verify the connection

```bash
python -m operation_drake.main --check-notion
```

Expected output:
```
  D.R.A.K.E. -- Notion Check
  Notion enabled       yes
  API token            present
  Database ID          configured
  Schema               compatible
  Connection           OK
```

---

## Existing database mode

If you already have a correctly structured database, set `NOTION_DATABASE_ID` directly and skip `--setup-notion`. Run `--check-notion` to verify schema compatibility.

---

## Database schema

The D.R.A.K.E. Knowledge Vault contains these properties:

| Property | Type | Purpose |
|---|---|---|
| Name | Title | Auto-generated concise title |
| Project | Select | Which project owns this item |
| Content Type | Select | What kind of content it is |
| Status | Select | Inbox / Organized / Needs Review / Action Required / Archived |
| Source | Select | Where it came from (Telegram Text, Voice, etc.) |
| Capture Context | Select | When/where it was captured (Pre-work Drive, etc.) |
| Captured At | Date | Original capture timestamp |
| Summary | Rich text | 2–3 sentence summary |
| Actionable | Checkbox | Whether it requires follow-up |
| Next Action | Rich text | Most important next step |
| Tags | Multi-select | Topic tags |
| Confidence | Number | Classification confidence 0–1 |
| Source URL | URL | Original URL if applicable |
| D.R.A.K.E. Task ID | Rich text | Links back to local task |
| D.R.A.K.E. Artifact ID | Rich text | Links back to local artifact |
| Sync Status | Select | Synced / Pending / Failed / Needs Review |

---

## Classification behavior

Every completed workflow is classified by an LLM before syncing.

### Projects

General, Business Ideas, The Answer Movement, Ascend, Operation D.R.A.K.E., DK Personal Health OS, Career & Work, School & Learning, Health & Fitness, Investing & Finance, Relationships & Networking, Personal Life

### Content types

Idea, Reflection, Research, Resource, Action Plan, Meeting Note, Decision, Journal Entry, Workday Check-in, Article or Media Capture, Voice Memo, General Note

### Capture contexts

General, Pre-work Drive, Post-work Drive, Commute, Work, School, Workout, Evening Reflection, Weekend Planning

---

## Explicit overrides

You can override classification directly in your message:

```
"Save this under The Answer Movement"         → Project: The Answer Movement
"This is an Ascend idea"                      → Project: Ascend
"This is a personal reflection"               → Content Type: Reflection
"Put this in business ideas"                  → Project: Business Ideas
"Do not save this to Notion"                  → sync skipped, saved locally only
"Don't sync this"                             → sync skipped
```

Explicit instructions take priority over inferred classification.

---

## Low-confidence behavior

When classification confidence is below `NOTION_LOW_CONFIDENCE_THRESHOLD` (default 0.70):

- Project defaults to `General`
- Status is set to `Needs Review`
- A note appears in the Telegram response: *"saved to Needs Review — classification was uncertain"*
- The item is still saved locally and synced to Notion

Review the **Needs Review** filtered view in Notion periodically to reclassify items.

---

## Notion failure behavior

If Notion sync fails:

1. The local workflow completes normally
2. The task stays `completed` in the local database
3. A `notion_syncs` record is saved with `sync_status=failed`
4. Telegram shows: *"Notion: pending (will retry with /sync_pending)"*
5. The item is never lost

---

## Telegram commands

| Command | Effect |
|---|---|
| `/notion` | Show Notion status: enabled, database connected, pending/failed counts, last sync time |
| `/sync <task_id>` | Retry Notion sync for one specific task |
| `/sync_pending` | Retry all pending and failed syncs (up to 20 at a time) |

---

## Disabling Notion

Set `NOTION_ENABLED=false` in `.env` and restart. All existing workflows continue unchanged. Local tasks, artifacts, and the Telegram bot are unaffected.

---

## Idempotency

The same task never creates two Notion pages, even if:

- The Telegram reply fails after Notion accepted the request
- The container restarts between sync and reply
- The user retries the same message
- `/sync_pending` runs multiple times

Each task has one idempotency key (`notion:<task_id>`). The sync service checks this before attempting to create a page.

---

## Future: CarPlay and ChatGPT Voice

The schema already supports future voice sources via:

- `Source = "ChatGPT Voice"` (defined, not yet used)
- `Capture Context = "Pre-work Drive"` / `"Post-work Drive"` (used by voice memo classification today)

When a future ChatGPT or CarPlay ingestion path is added, it will map to these existing properties without requiring a schema change. The intended future flow:

```
Voice conversation (ChatGPT / CarPlay)
→ transcript or export
→ D.R.A.K.E. normalization
→ project routing
→ Notion organization with Pre-work Drive / Post-work Drive context
```

This is a roadmap item — no placeholder code exists yet.

---

## Production deployment notes

Before deploying with `NOTION_ENABLED=true`:

1. Run `scripts/backup.sh` on the server to back up the database
2. Run `python -m operation_drake.main --check-notion` locally to verify
3. Deploy with `scripts/deploy.sh` — the `notion_syncs` table is created automatically by SQLAlchemy `create_all` (additive, safe for existing data)
4. Run `python -m operation_drake.main --check-notion` inside the container to verify connection
5. Send a test message and confirm Notion sync appears in the Telegram response

Rollback: set `NOTION_ENABLED=false` and restart. No schema rollback needed.
