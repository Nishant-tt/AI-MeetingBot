"""Outlook / Microsoft 365 Calendar: OAuth connect + list upcoming meetings.

Setup (one time):
  1. Azure Portal -> App registrations -> New registration.
  2. Redirect URI (Web): http://localhost:8000/calendars/microsoft/callback
  3. API permissions (delegated): Calendars.Read, User.Read, offline_access.
  4. Certificates & secrets -> new client secret.
  5. Put client id/secret in .env (MS_CLIENT_ID / MS_CLIENT_SECRET).
"""
from datetime import datetime, timedelta, timezone

import msal
import requests

from ..config import settings
from .extract import extract_meeting_url, parse_iso

AUTHORITY = "https://login.microsoftonline.com/common"
SCOPES = ["Calendars.Read", "User.Read"]  # MSAL adds offline_access/openid itself
GRAPH = "https://graph.microsoft.com/v1.0"


def _app() -> msal.ConfidentialClientApplication:
    return msal.ConfidentialClientApplication(
        client_id=settings.ms_client_id,
        authority=AUTHORITY,
        client_credential=settings.ms_client_secret,
    )


def get_auth_url(state: str) -> str:
    return _app().get_authorization_request_url(
        scopes=SCOPES, redirect_uri=settings.ms_redirect_uri, state=state
    )


def exchange_code(code: str) -> dict:
    result = _app().acquire_token_by_authorization_code(
        code, scopes=SCOPES, redirect_uri=settings.ms_redirect_uri
    )
    if "access_token" not in result:
        raise RuntimeError(result.get("error_description", "Token exchange failed"))
    claims = result.get("id_token_claims", {})
    return {
        "email": claims.get("preferred_username") or claims.get("email"),
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token"),
        "token_expiry": datetime.now(timezone.utc)
        + timedelta(seconds=result.get("expires_in", 3600)),
    }


def _access_token(account) -> str:
    """Refresh the access token from the stored refresh token."""
    if not account.refresh_token:
        return account.access_token
    result = _app().acquire_token_by_refresh_token(account.refresh_token, scopes=SCOPES)
    return result.get("access_token", account.access_token)


def list_upcoming(account) -> list[dict]:
    token = _access_token(account)
    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=settings.calendar_window_hours)

    params = {
        "startDateTime": now.isoformat(),
        "endDateTime": end.isoformat(),
        "$select": "subject,start,end,onlineMeeting,onlineMeetingUrl,location,bodyPreview",
        "$orderby": "start/dateTime",
        "$top": "50",
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Prefer": 'outlook.timezone="UTC"',
    }
    r = requests.get(f"{GRAPH}/me/calendarView", headers=headers, params=params, timeout=30)
    r.raise_for_status()

    out = []
    for ev in r.json().get("value", []):
        start = parse_iso((ev.get("start") or {}).get("dateTime"))
        if not start:
            continue
        url = (ev.get("onlineMeeting") or {}).get("joinUrl") or ev.get("onlineMeetingUrl")
        if not url:
            loc = (ev.get("location") or {}).get("displayName")
            url = extract_meeting_url(loc, ev.get("bodyPreview"))
        if not url:
            continue
        out.append({
            "event_id": ev.get("id"),
            "title": ev.get("subject") or "Meeting",
            "start": start,
            "meeting_url": url,
        })
    return out
