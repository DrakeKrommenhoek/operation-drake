"""Google OAuth 2.0 for the Google Health API v4 (read-only).

Loopback flow (redirect http://127.0.0.1:3000/callback) on first run; token cached
to disk and silently refreshed on every subsequent call. Read-only scopes only --
write methods are not requested and are not yet granted to third-party clients
regardless.
"""

from __future__ import annotations

import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from health.config import get_settings

# Confirmed at https://developers.google.com/health/scopes.
# If consent fails with "invalid_scope", verify current scope strings via the
# OAuth 2.0 Playground scope picker (https://developers.google.com/oauthplayground)
# before assuming this list is stale.
#
# health_metrics_and_measurements.readonly was added after activity_and_fitness
# alone produced 403 "Required OAuth scope(s) are missing" on resting-heart-rate
# and heart-rate-variability reconcile calls (confirmed live) -- those two data
# types apparently live under the metrics/measurements scope, not activity/fitness.
SCOPES = [
    "https://www.googleapis.com/auth/googlehealth.sleep.readonly",
    "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
    "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly",
]


def _client_config(settings) -> dict:
    return {
        "installed": {
            "client_id": settings.client_id,
            "client_secret": settings.client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.redirect_uri],
        }
    }


def get_credentials() -> Credentials:
    """Return valid, refreshed OAuth credentials, running the consent flow if needed."""
    settings = get_settings()

    creds: Credentials | None = None
    if settings.token_path.exists():
        creds = Credentials.from_authorized_user_file(str(settings.token_path), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _persist(creds, settings)
        return creds

    if not settings.client_id or not settings.client_secret:
        raise RuntimeError(
            "GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET are not set. "
            "Copy health/.env.example to health/.env and fill them in first "
            "(see health/README.md for Google Cloud Console setup)."
        )

    flow = InstalledAppFlow.from_client_config(_client_config(settings), SCOPES)
    port = int(settings.redirect_uri.rsplit(":", 1)[1].split("/")[0])
    creds = flow.run_local_server(port=port)
    _persist(creds, settings)
    return creds


def _persist(creds: Credentials, settings) -> None:
    settings.token_path.parent.mkdir(parents=True, exist_ok=True)
    settings.token_path.write_text(creds.to_json(), encoding="utf-8")
    try:
        settings.token_path.chmod(0o600)
    except NotImplementedError:
        pass  # chmod is a no-op on some Windows filesystems; VPS (Linux) honors it.


if __name__ == "__main__":
    creds = get_credentials()
    print(json.dumps({"valid": creds.valid, "scopes": creds.scopes}, indent=2))
