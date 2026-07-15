"""Connection-proof command, modeled on google-health-mcp's `doctor` pattern.

Authenticates against the Google Health API and prints yesterday's sleep summary.
Run this after Google Cloud Console setup and before enabling any cron schedule --
per the Phase 1 soak rule, nothing gets scheduled until this passes.

Usage:
    python -m health.verify
"""

from __future__ import annotations

from datetime import date, timedelta

from health import client
from health.auth import get_credentials
from health.ingest import _parse_sleep_minutes


def main() -> None:
    target = date.today() - timedelta(days=1)

    print("Authenticating (opens a browser on first run; redirect -> 127.0.0.1)...")
    creds = get_credentials()
    print(f"OK -- credentials valid, scopes: {creds.scopes}")

    print(f"Fetching sleep for {target.isoformat()} via reconcile...")
    raw_sleep = client.reconcile(creds, "sleep", target)
    minutes = _parse_sleep_minutes(raw_sleep)

    if minutes is not None:
        hours = minutes // 60
        mins = minutes % 60
        print(f"OK -- {target.isoformat()} sleep: {int(hours)}h {int(mins)}m ({minutes} min)")
    else:
        print(
            f"Connected, but could not parse a sleep duration for {target.isoformat()}.\n"
            "This can mean no sleep session was recorded that night, or the API's\n"
            "nested field names differ from what ingest.py expects. Raw response:\n"
        )
        print(raw_sleep)

    print("\nGoogle Health API connection verified.")


if __name__ == "__main__":
    main()
