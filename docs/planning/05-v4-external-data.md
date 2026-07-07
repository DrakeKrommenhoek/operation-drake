# v4: External Data

Effort: TBD. Prereq: v1-v3 running clean for a full month. Do NOT start any module here early.

## Module A: Health (BLOCKED)

**Blocker: the Fitbit vs. Apple Watch decision. Make it before writing one line of ingest code.** The DK_0726 sequencing rule already requires 14 days of Phase 0 manual logging first; that project owns the pipeline. This module only CONSUMES its output.

When unblocked:
- Weekly pull: sleep score, resting HR, steps, active minutes.
- Feeds one section into the Sunday digest: this week vs 4-week average, one-line trend commentary.
- No raw health data in the repo, ever. Aggregates only, stored in SQLite on the VPS.

## Module B: Voice Reflections

Skip the ChatGPT CarPlay export problem entirely. It has no API for conversation export worth fighting.

- New habit: commute reflections go as Telegram voice notes to the bot (30-60 seconds at red lights is enough; never while actively driving).
- Existing pipeline already handles Telegram Voice source type: transcribe, classify as Reflection, Capture Context = Pre-work Drive or Post-work Drive based on time of day.
- Sunday digest gains: "This week you reflected on..." with 2-3 themes extracted across the week's reflections.
- Zero new integrations. This is a behavior change plus one Claude call, not a build.

## Module C: Stock Research

**Compliance is the architecture here, not a feature.**

- Watchlist stored as a simple Notion page or SQLite table of tickers plus one-line theses.
- Weekly cron: for each ticker, pull recent news and price action via web search, compose a 3-line update (what changed, thesis intact or broken, no recommendation language).
- Feeds one section into the Sunday digest.
- **HARD RULES, enforced in code:**
  - No order placement capability anywhere in this system. No broker API keys on the VPS.
  - Every stock section footer: "Pre-clearance required before any trade."
  - Retail-adjacent names tied to Mountaingate portfolio companies are excluded from the watchlist entirely.
- Saved stock-pick videos: store link plus one-line thesis in the vault, nothing else. No video storage.

## Done when
- Sunday digest contains health, reflections, and watchlist sections for 4 consecutive weeks.
- Zero compliance rule violations (this metric is pass/fail).

## Gotchas
- Fitbit OAuth tokens expire; refresh flow needs to run headless on the VPS with tokens in env vars, never committed.
- If any module fails, the digest still sends with a "section unavailable" line. Partial digest beats no digest.
