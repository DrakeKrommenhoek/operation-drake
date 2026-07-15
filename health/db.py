"""SQLite access for health/ -- stdlib sqlite3 only, no SQLAlchemy.

Talks to the same database file as the D.R.A.K.E. bot but owns a table the bot
never touches (health_daily_metrics). This is the only shared surface with the
rest of the repo; do not import operation_drake.* from here.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

from health.config import get_settings

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    settings = get_settings()
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path)
    conn.execute(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


def upsert_daily_metrics(conn: sqlite3.Connection, day: date, metrics: dict) -> None:
    """Idempotent upsert of one day's parsed + raw metrics, keyed on date."""
    row = {
        "date": day.isoformat(),
        "steps": metrics.get("steps"),
        "resting_heart_rate": metrics.get("resting_heart_rate"),
        "hrv_ms": metrics.get("hrv_ms"),
        "active_zone_minutes": metrics.get("active_zone_minutes"),
        "sleep_minutes": metrics.get("sleep_minutes"),
        "raw_steps": metrics.get("raw_steps"),
        "raw_resting_heart_rate": metrics.get("raw_resting_heart_rate"),
        "raw_hrv": metrics.get("raw_hrv"),
        "raw_active_zone_minutes": metrics.get("raw_active_zone_minutes"),
        "raw_sleep": metrics.get("raw_sleep"),
        "ingested_at": datetime.now(UTC).isoformat(),
    }
    columns = ", ".join(row.keys())
    placeholders = ", ".join(f":{k}" for k in row)
    updates = ", ".join(f"{k} = excluded.{k}" for k in row if k != "date")
    conn.execute(
        f"""
        INSERT INTO health_daily_metrics ({columns})
        VALUES ({placeholders})
        ON CONFLICT(date) DO UPDATE SET {updates}
        """,
        row,
    )
    conn.commit()
