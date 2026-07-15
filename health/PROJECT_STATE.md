# DK_0726 Personal Health OS: project state (updated 2026-07-15)

## What it is
A private, single-user personal health operating system. One job: correlate supplement intake and daily habits against wearable biometric data, explain observations in plain language, and suggest one low-risk, testable adjustment at a time. Evidence layer for an n-of-1 experiment. Not a dashboard, not medical advice, not a consumer app replacement. Single user (Drake). No multi-user, no SaaS, no app-store ambitions.

Core sentence: Wearable numbers in, supplement and habit evidence in, plain-language interpretation out.

## Status
- Phase 0 (14-day manual logging gate): COMPLETE as of 2026-07-15. 10+ clean days logged. Witness confirmation to a named person still required per gate rule.
- Phase 1a (Google Cloud OAuth setup): COMPLETE as of 2026-07-15. OAuth client created, scopes registered (sleep.readonly, activity_and_fitness.readonly, health_metrics_and_measurements.readonly -- the third one was missing from the original plan and had to be added after resting-heart-rate/HRV calls came back 403).
- Phase 1b (ingest pipeline): CODE COMPLETE AND LIVE-VERIFIED as of 2026-07-15. `python -m health.verify` and `python -m health.ingest` both run successfully against the live API for 2026-07-14: steps=4707, resting_hr=61.0 bpm, hrv=146.8ms (avg RMSSD), active_zone_minutes=6, sleep=405min. All values cross-checked against raw API responses, not just "ran without error." **Not yet scheduled on cron** -- per the soak rule, cron activation is a separate decision, not automatic after verify passes.
- Device decision: RESOLVED. Fitbit Air is the nightly-wear device. Data lives in Google Health.

### Phase 1b build notes (corrections to the original plan above)
The API surface differs from what's assumed elsewhere in this doc, discovered empirically (docs alone were unreliable/incomplete for exact field names and per-data-type support):
- Only `steps` and `active-zone-minutes` support `dailyRollUp`. `sleep`, `heart-rate-variability`, and `daily-resting-heart-rate` all return `UNSUPPORTED_DATA_TYPE_ACTION` for `dailyRollUp` and must use `reconcile` instead.
- `reconcile`'s `filter` query param needs a data-type-prefixed member name, and both the valid member name and its value format (RFC3339 timestamp vs. bare civil date) vary per data type's record type (Session/Sample/Daily) -- see the detailed docstring in `health/client.py::reconcile`.
- `heart-rate-variability` returns one sample roughly every 5 minutes -- the default `pageSize=25` silently truncates a full day to under 2 hours of data. `health/ingest.py` requests `page_size=500` for HRV specifically.
- See `health/client.py` and `health/ingest.py` for the exact confirmed request/response shapes.

## Placement decision (2026-07-15)
This project lives inside the Operation D.R.A.K.E. repo as a self-contained subdirectory: `health/`. Rationale: the D.R.A.K.E. VPS agent is the eventual consumer of this data, both share the same VPS and SQLite-plus-cron backbone, and centralizing avoids a future sync problem. Boundary rule: `health/` has its own module, its own cron entries, and its own env vars. It must not import from or be imported by the Telegram capture bot code. Shared surface is the SQLite database file only.

## Technical foundation
- API: Google Health API v4 (`https://health.googleapis.com/v4/`), Google OAuth 2.0 via Google Cloud Console client. NOT the legacy Fitbit Web API (sunsets September 2026; tokens do not carry over).
- API surface: 31 data types, one URL template (`users/me/dataTypes/{dataType}/dataPoints`), four read methods: list, reconcile, rollUp, dailyRollUp. Use reconcile-based methods so multi-source data is merged. Intraday resolution (5-second heart rate) is default, no approval tier needed. Write methods exist in the discovery doc but are not yet granted to third-party clients: read-only pipeline.
- JSON shape is fully nested (data type plus dataSource wrapper), nothing like the old flat Fitbit responses. Do not reuse any legacy Fitbit parsing patterns.
- Known limitation: nutrition data is NOT in the Google Health API. Food and supplement logging comes from the Telegram intake pipeline, not the device. This is by design: the correlation layer is the product.

## Inspiration repos
1. davidmosiah/google-health-mcp: local-first MCP server exposing Google Health API v4 data to Claude over OAuth, tokens never leave the machine. Two uses: (a) quick win, connect it to Claude Desktop/Code for immediate conversational access to Air data before any custom code exists; (b) reference implementation for the OAuth flow, scope presets, and its doctor/coverage validation pattern, which Phase 1 should copy as a `verify` command.
2. arpanghosh8453/fitbit-grafana: reference for the polling loop, token refresh persistence, and time-series storage patterns. Now supports a Google provider mode. We swap InfluxDB/Grafana for SQLite; the scheduling and token-handling patterns transfer.
3. Terra's Google Health API v4 deep dive (tryterra.co blog): the practical API bible. Includes a ~30-line stdlib Python pagination pattern for dataPoints pulls.

## Phase 1 build plan
- 1a (one evening): Google Cloud project, enable Google Health API, OAuth client, redirect `http://127.0.0.1:3000/callback`. Validate reachability using the google-health-mcp setup/auth/doctor flow before writing any code.
- 1b (one weekend session): `health/ingest.py` on the DigitalOcean VPS. Daily 6am cron. Pull dailyRollUp for: sleep, restingHeartRate, hrv, steps, activeZoneMinutes. Idempotent upserts into SQLite keyed on date. `health/auth.py` handles OAuth with token refresh persisted to disk. Read-only scopes. Config via .env. Roughly 150 lines. No agent frameworks, no orchestration platforms. SQLite plus cron until something actually breaks.
- 1c (one weekend session): Sunday-night cron pulls the week from SQLite plus Telegram-logged supplements and meals from Notion, sends both to the Claude API, writes a plain-language weekly correlation report back to Notion. One suggested adjustment per week maximum.
- Soak rule: 14 days between phases. One phase at a time.

## Hard constraints
- Tree-nut allergy is a non-negotiable filter on any supplement or product suggestion the insight layer ever makes.
- Mountaingate compliance: no firm work product in this repo, no MNPI, pre-clearance before personal trades. Health OS has no market-data surface; keep it that way.
- Tech environment: Windows 11 dev machine, PowerShell only, no bash chaining locally. VPS is Ubuntu (cron lives there).
- Insight tone: observations and plain language, never diagnosis.

## Where the evidence lives
Phase 0 logs: daily-evidence tracker (Notion vault / Telegram capture). D.R.A.K.E. Command Center page tracks this project's lane and gate history.
