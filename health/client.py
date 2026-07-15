"""Thin stdlib HTTP client for the Google Health API v4.

https://health.googleapis.com/v4/ -- NOT the legacy Fitbit Web API. No legacy
flat-JSON parsing patterns apply here; every payload is nested (data type plus
dataSource wrapper).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

from google.auth.credentials import Credentials

API_BASE = "https://health.googleapis.com/v4"


class GoogleHealthAPIError(RuntimeError):
    def __init__(self, status: int, body: str):
        super().__init__(f"Google Health API returned {status}: {body}")
        self.status = status
        self.body = body


def _civil_date_time(d: date) -> dict:
    """CivilDateTime wrapper the API actually expects (confirmed live).

    A flat {"year", "month", "day"} at range.start/end is rejected with
    "Unknown name 'year'" -- CivilDateTime nests calendar date under "date".
    """
    return {"date": {"year": d.year, "month": d.month, "day": d.day}}


def _request(creds: Credentials, method: str, path: str, body: dict | None) -> dict:
    url = f"{API_BASE}/{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {creds.token}")
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise GoogleHealthAPIError(exc.code, exc.read().decode("utf-8", "replace")) from exc


def daily_roll_up(creds: Credentials, data_type: str, target: date) -> dict:
    """POST dataPoints:dailyRollUp for a single civil day of a given dataType.

    The range is closed-open (confirmed live): start == end is rejected with
    INVALID_DATA_POINT_NAME, so end must be the following civil day to select
    exactly one day of data.
    """
    next_day = target + timedelta(days=1)
    body = {
        "range": {"start": _civil_date_time(target), "end": _civil_date_time(next_day)},
        "windowSizeDays": 1,
    }
    return _request(
        creds, "POST", f"users/me/dataTypes/{data_type}/dataPoints:dailyRollUp", body
    )


def reconcile(
    creds: Credentials,
    data_type: str,
    target: date,
    time_field: str = "interval.end_time",
    civil: bool = False,
    page_size: int = 25,
) -> dict:
    """GET dataPoints:reconcile for a single civil day of a given dataType.

    Used for data types not supported by dailyRollUp (currently: sleep,
    heart-rate-variability, daily-resting-heart-rate).

    Filter fields must be prefixed with the data type name (AIP-160), e.g.
    "sleep.interval.end_time" -- a bare "start_time" is rejected with
    INVALID_DATA_POINT_FILTER_RESTRICTION_COMPARABLE. The valid temporal member
    name and value format both vary by data type (confirmed empirically against
    the live API, not from docs alone -- several plausible-looking members are
    flat-out rejected as INVALID_DATA_POINT_FILTER_DATA_TYPE_MEMBER):
      - sleep (Session record type): "interval.end_time", RFC3339 timestamp.
      - heart-rate-variability (Sample record type): "sample_time.physical_time",
        RFC3339 timestamp. This type returns one sample roughly every 5 minutes,
        so a full day needs a larger page_size than the 25-row default (which is
        fine for sleep/resting-heart-rate, one row per night/day) -- ingest.py
        passes page_size=500 for HRV. Full pagination via nextPageToken isn't
        implemented; 500 covers a full day of 5-minute samples with headroom,
        acceptable for a single-user personal tool.
      - daily-resting-heart-rate (Daily record type): "date", bare civil date
        (YYYY-MM-DD) -- pass civil=True, RFC3339 timestamps are rejected with
        INVALID_DATA_POINT_FILTER_CIVIL_DATE_TIME_FORMAT on this field.
    """
    field_prefix = data_type.replace("-", "_")
    next_day = target + timedelta(days=1)
    if civil:
        start_value, end_value = target.isoformat(), next_day.isoformat()
    else:
        start_value = f"{target.isoformat()}T00:00:00Z"
        end_value = f"{next_day.isoformat()}T00:00:00Z"
    filter_expr = (
        f'{field_prefix}.{time_field} >= "{start_value}" AND '
        f'{field_prefix}.{time_field} < "{end_value}"'
    )
    qs = urllib.parse.urlencode({"filter": filter_expr, "pageSize": page_size})
    return _request(
        creds, "GET", f"users/me/dataTypes/{data_type}/dataPoints:reconcile?{qs}", None
    )
