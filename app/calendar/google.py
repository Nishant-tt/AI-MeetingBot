"""Google Calendar: OAuth connect + list upcoming meetings.

Setup (one time):
  1. Google Cloud Console -> create OAuth 2.0 Client ID (type: Web application).
  2. Add redirect URI: http://localhost:8000/calendars/google/callback
  3. Enable the Google Calendar API for the project.
  4. Put the client id/secret in .env (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET).
"""
from datetime import datetime, timedelta, timezone

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from ..config import settings
from .extract import extract_meeting_url, parse_iso

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]


def _client_config() -> dict:
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }


def _flow() -> Flow:
    return Flow.from_client_config(
        _client_config(), scopes=SCOPES, redirect_uri=settings.google_redirect_uri
    )


def get_auth_url() -> tuple[str, str]:
    flow = _flow()
    url, state = flow.authorization_url(
        access_type="offline", prompt="consent", include_granted_scopes="true"
    )
    return url, state


def exchange_code(code: str) -> dict:
    """Exchange the auth code for tokens; also fetch the account email."""
    flow = _flow()
    flow.fetch_token(code=code)
    creds = flow.credentials

    email = None
    try:
        oauth2 = build("oauth2", "v2", credentials=creds)
        email = oauth2.userinfo().get().execute().get("email")
    except Exception:
        pass

    return {
        "email": email,
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_expiry": creds.expiry.replace(tzinfo=timezone.utc) if creds.expiry else None,
    }


def _credentials(account) -> Credentials:
    creds = Credentials(
        token=account.access_token,
        refresh_token=account.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=SCOPES,
    )
    if creds.refresh_token and (not creds.valid):
        creds.refresh(Request())
    return creds


def list_upcoming(account) -> list[dict]:
    """Return upcoming events that have a meeting link, within the scan window."""
    creds = _credentials(account)
    service = build("calendar", "v3", credentials=creds)

    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=settings.calendar_window_hours)
    resp = service.events().list(
        calendarId="primary",
        timeMin=now.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        maxResults=50,
    ).execute()

    out = []
    for ev in resp.get("items", []):
        start = parse_iso((ev.get("start") or {}).get("dateTime"))  # None => all-day
        if not start:
            continue
        url = ev.get("hangoutLink")
        if not url:
            for ep in (ev.get("conferenceData") or {}).get("entryPoints", []):
                if ep.get("entryPointType") == "video":
                    url = ep.get("uri")
                    break
        if not url:
            url = extract_meeting_url(ev.get("location"), ev.get("description"))
        if not url:
            continue
        out.append({
            "event_id": ev["id"],
            "title": ev.get("summary") or "Meeting",
            "start": start,
            "meeting_url": url,
        })
    return out
