-- health_daily_metrics: one row per calendar day, upserted idempotently by health/ingest.py.
-- Lives in the same SQLite file as the D.R.A.K.E. bot (data/database/agent.db) but this
-- table is owned exclusively by health/ -- the bot's ORM never reads or writes it.
CREATE TABLE IF NOT EXISTS health_daily_metrics (
    date TEXT PRIMARY KEY,              -- ISO date, e.g. 2026-07-14

    steps INTEGER,
    resting_heart_rate REAL,
    hrv_ms REAL,
    active_zone_minutes INTEGER,
    sleep_minutes INTEGER,

    -- Full raw API response per metric, kept alongside the parsed columns above so no
    -- data is lost if a parsed field name assumption turns out wrong once verify runs
    -- against the live API.
    raw_steps TEXT,
    raw_resting_heart_rate TEXT,
    raw_hrv TEXT,
    raw_active_zone_minutes TEXT,
    raw_sleep TEXT,

    ingested_at TEXT NOT NULL            -- UTC ISO timestamp of last upsert
);
