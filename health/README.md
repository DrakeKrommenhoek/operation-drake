# health/ -- Personal Health OS (Phase 1b)

Self-contained module. Correlates wearable biometric data (Google Health API v4,
sourced from a Fitbit Air) against supplement/habit logging that lives elsewhere
(the Telegram capture pipeline / Notion). See `PROJECT_STATE.md` for the full
project brief, phase plan, and hard constraints.

## Boundary rule

`health/` does not import from, or get imported by, the D.R.A.K.E. bot code in
`src/operation_drake/`. The only shared surface is the SQLite database file
(`data/database/agent.db`) -- this module owns one table in it
(`health_daily_metrics`) via plain `sqlite3`, not the bot's SQLAlchemy models.

## Google Cloud Console setup (one-time)

1. Go to [console.cloud.google.com](https://console.cloud.google.com/) and create
   a project (or reuse an existing personal one).
2. **APIs & Services -> Library**: search "Google Health API", enable it.
3. **APIs & Services -> OAuth consent screen -> Audience**
   ([console.cloud.google.com/auth/audience](https://console.cloud.google.com/auth/audience)):
   confirm **User type = External** and **Publishing status = Testing**, then
   under "Test users" click **+ Add users** and add your own Google account.
   Google Health scopes are restricted, single-user personal apps like this can
   stay in Testing indefinitely (capped at 100 users, which we'll never hit).
4. **APIs & Services -> OAuth consent screen -> Data access**
   ([console.cloud.google.com/auth/scopes](https://console.cloud.google.com/auth/scopes)):
   click **Add or remove scopes**, search "Google Health API," and select the
   three read-only scopes this module requests (`googlehealth.sleep.readonly`,
   `googlehealth.activity_and_fitness.readonly`,
   `googlehealth.health_metrics_and_measurements.readonly` -- the third one
   covers resting heart rate and HRV specifically; without it those two calls
   fail with a 403 even though steps/sleep/active-zone-minutes work fine).
   Click **Update**, then **Save**.
   **This step is easy to miss** -- restricted scopes must be explicitly
   registered here even though the OAuth client itself doesn't list them, and
   skipping it produces `Access blocked: ... has not completed the Google
   verification process` at consent time even with a test user added.
5. **APIs & Services -> Credentials -> Create Credentials -> OAuth client ID**:
   - Application type: **Desktop app**
   - Add an **Authorized redirect URI**: `http://127.0.0.1:3000/callback`
   - Download the client ID and secret.
6. Copy `health/.env.example` to `health/.env` and fill in
   `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET`.

## Install

```powershell
pip install -r health\requirements.txt
```

## First-time auth

```powershell
python -m health.auth
```

Opens a browser to Google's consent screen, then redirects to
`http://127.0.0.1:3000/callback`. Token is cached to `health/.token.json`
(gitignored, `chmod 600` on Linux) and auto-refreshed after that -- no need to
re-run this unless the token file is deleted or access is revoked.

**Before running this for the first time, confirm `health/.token.json` is listed
in `health/.gitignore`** (it is, by default) so a credential never lands in Git.

## Verify (run before any cron scheduling)

```powershell
python -m health.verify
```

Authenticates and prints yesterday's sleep summary as the connection proof --
this is the same role `doctor --live` plays in the google-health-mcp reference
project. Do not add the cron entry below until this passes.

If OAuth consent fails with `invalid_scope`, the scope strings in `health/auth.py`
may be stale -- cross-check them against the current list in the
[OAuth 2.0 Playground](https://developers.google.com/oauthplayground) scope
picker before changing anything.

## Ingest

```powershell
python -m health.ingest                    # yesterday
python -m health.ingest --date 2026-07-14  # specific date
```

Pulls `dailyRollUp` for steps, resting heart rate, HRV, and active zone minutes,
and `reconcile` for sleep (sleep isn't part of the `dailyRollUp` response union).
Upserts one row per date into `health_daily_metrics`, keyed on `date` -- safe to
re-run for the same day.

Every metric's full raw API response is stored alongside the parsed columns
(`raw_steps`, `raw_sleep`, etc.). A few nested field names (resting-HR range,
HRV range, sleep stage shape) weren't fully confirmed from the public docs at
scaffold time -- if `verify` or `ingest` shows a parsed column as `NULL` where
data should exist, inspect the matching `raw_*` column in SQLite and adjust the
parser in `health/ingest.py`.

## VPS cron (after verify passes)

See the "health/ Cron" section appended to `docs/vps-deployment.md`. Daily 6am
pull, plain cron job (not a Docker container) since this module has no server
process to run. Per the Phase 1 soak rule, wait 14 days before starting Phase 1c
(weekly correlation report).

## Not in scope for Phase 1b

- Phase 1c (weekly Claude correlation report to Notion)
- Supplement/meal ingestion (comes from the Telegram pipeline, not this module --
  nutrition data isn't in the Google Health API)
- Any write access to Google Health (read-only scopes only; write methods aren't
  granted to third-party clients yet regardless)
