"""Pull yesterday's (or a given date's) Google Health data and upsert it into SQLite.

Usage:
    python -m health.ingest                  # yesterday (default -- dailyRollUp needs a closed day)
    python -m health.ingest --date 2026-07-14

Data types pulled via dailyRollUp (confirmed to support the rollup union):
    steps, daily-resting-heart-rate, heart-rate-variability, active-zone-minutes
Sleep is pulled via reconcile instead -- it is not part of the dailyRollUp union.

Idempotent: re-running for the same date overwrites that date's row (upsert keyed
on date), it never inserts duplicates.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta

from health import client, db
from health.auth import get_credentials


def _iso_duration_to_minutes(start_iso: str, end_iso: str) -> float | None:
    """Best-effort RFC3339 timestamp difference, in minutes."""
    from datetime import datetime

    try:
        start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
        return (end - start).total_seconds() / 60
    except (ValueError, AttributeError, TypeError):
        return None


def _parse_steps(payload: dict) -> int | None:
    points = payload.get("rollupDataPoints", [])
    for point in points:
        steps = point.get("steps")
        if steps and "countSum" in steps:
            return int(steps["countSum"])
    return None


def _parse_active_zone_minutes(payload: dict) -> int | None:
    points = payload.get("rollupDataPoints", [])
    for point in points:
        azm = point.get("activeZoneMinutes")
        if azm:
            return sum(
                int(azm.get(key, 0) or 0)
                for key in (
                    "sumInCardioHeartZone",
                    "sumInPeakHeartZone",
                    "sumInFatBurnHeartZone",
                )
            )
    return None


def _first_numeric(obj: dict, keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = obj.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def _parse_resting_heart_rate(payload: dict) -> float | None:
    """Parse a reconcile() response for daily-resting-heart-rate.

    Confirmed live shape: {"dataPoints": [{"dailyRestingHeartRate":
    {"date": {...}, "beatsPerMinute": "61", "dailyRestingHeartRateMetadata": {...}}}]}.
    Other container/key names kept as a defensive fallback only.
    """
    for point in payload.get("dataPoints", []):
        for container_key in ("dailyRestingHeartRate", "restingHeartRate", "heartRate"):
            container = point.get(container_key)
            if not container:
                continue
            value = _first_numeric(
                container, ("beatsPerMinute", "value", "average", "beatsPerMinuteMin")
            )
            if value is not None:
                return value
            lo, hi = container.get("beatsPerMinuteMin"), container.get("beatsPerMinuteMax")
            if lo is not None and hi is not None:
                return (float(lo) + float(hi)) / 2
    return None


def _parse_hrv(payload: dict) -> float | None:
    """Average RMSSD across all HRV samples returned for the day.

    Confirmed live shape: {"dataPoints": [{"heartRateVariability":
    {"sampleTime": {...}, "rootMeanSquareOfSuccessiveDifferencesMilliseconds": 189}}, ...]},
    with one sample roughly every 5 minutes (see page_size note in client.reconcile).
    """
    values = []
    for point in payload.get("dataPoints", []):
        container = point.get("heartRateVariability")
        if not container:
            continue
        value = container.get("rootMeanSquareOfSuccessiveDifferencesMilliseconds")
        if value is not None:
            values.append(float(value))
    return round(sum(values) / len(values), 1) if values else None


def _parse_sleep_minutes(payload: dict) -> int | None:
    """Sum minutes asleep across all sleep sessions returned for the day.

    Confirmed shape (from a live reconcile response, 2026-07-15): each entry in
    payload["dataPoints"] has a "sleep" object with sleep["summary"]["minutesAsleep"]
    already computed by the API -- no need to re-derive it from stage timestamps.
    Falls back to summing non-AWAKE entries in sleep["stages"] (each stage has
    "type"/"startTime"/"endTime" directly, not nested under an "interval" key)
    if a session has no summary. Returns None (raw JSON is still stored) if
    neither shape matches -- inspect raw_sleep to adjust.
    """
    total_minutes = 0.0
    found = False

    for point in payload.get("dataPoints", []):
        sleep = point.get("sleep")
        if not sleep:
            continue

        minutes_asleep = (sleep.get("summary") or {}).get("minutesAsleep")
        if minutes_asleep is not None:
            total_minutes += float(minutes_asleep)
            found = True
            continue

        for stage in sleep.get("stages") or []:
            if stage.get("type") == "AWAKE":
                continue
            minutes = _iso_duration_to_minutes(stage.get("startTime"), stage.get("endTime"))
            if minutes is not None:
                total_minutes += minutes
                found = True

    return int(total_minutes) if found else None


def ingest_day(target: date) -> dict:
    creds = get_credentials()

    # Confirmed live: only steps and active-zone-minutes support dailyRollUp.
    # daily-resting-heart-rate and heart-rate-variability return
    # UNSUPPORTED_DATA_TYPE_ACTION for dailyRollUp -- API allows only list/reconcile.
    raw_steps = client.daily_roll_up(creds, "steps", target)
    raw_azm = client.daily_roll_up(creds, "active-zone-minutes", target)
    # heart-rate-variability is a "Sample" record type -> sample_time.physical_time.
    # page_size=500: ~5-minute sample cadence means the 25-row default truncates
    # a full day (confirmed live -- 25 rows covered under 2 hours).
    raw_hrv = client.reconcile(
        creds,
        "heart-rate-variability",
        target,
        time_field="sample_time.physical_time",
        page_size=500,
    )
    # daily-resting-heart-rate is a "Daily" record type -> bare civil "date" field
    # (confirmed live; RFC3339 timestamps on this field are rejected outright).
    raw_rhr = client.reconcile(
        creds, "daily-resting-heart-rate", target, time_field="date", civil=True
    )
    raw_sleep = client.reconcile(creds, "sleep", target)

    metrics = {
        "steps": _parse_steps(raw_steps),
        "resting_heart_rate": _parse_resting_heart_rate(raw_rhr),
        "hrv_ms": _parse_hrv(raw_hrv),
        "active_zone_minutes": _parse_active_zone_minutes(raw_azm),
        "sleep_minutes": _parse_sleep_minutes(raw_sleep),
        "raw_steps": json.dumps(raw_steps),
        "raw_resting_heart_rate": json.dumps(raw_rhr),
        "raw_hrv": json.dumps(raw_hrv),
        "raw_active_zone_minutes": json.dumps(raw_azm),
        "raw_sleep": json.dumps(raw_sleep),
    }

    conn = db.get_connection()
    try:
        db.upsert_daily_metrics(conn, target, metrics)
    finally:
        conn.close()

    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest one day of Google Health data.")
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        default=date.today() - timedelta(days=1),
        help="ISO date to ingest (default: yesterday).",
    )
    args = parser.parse_args()

    metrics = ingest_day(args.date)
    print(
        f"Ingested {args.date.isoformat()}: "
        f"steps={metrics['steps']} "
        f"resting_hr={metrics['resting_heart_rate']} "
        f"hrv_ms={metrics['hrv_ms']} "
        f"active_zone_minutes={metrics['active_zone_minutes']} "
        f"sleep_minutes={metrics['sleep_minutes']}"
    )


if __name__ == "__main__":
    main()
