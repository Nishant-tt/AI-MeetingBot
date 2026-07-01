import re
from datetime import datetime, timezone

# Matches Zoom / Google Meet / Microsoft Teams / Webex join links.
_URL_RE = re.compile(
    r"https?://[^\s\"'<>]*?"
    r"(?:zoom\.us/[js]/|meet\.google\.com/|teams\.microsoft\.com/|"
    r"teams\.live\.com/|webex\.com/)"
    r"[^\s\"'<>]+",
    re.IGNORECASE,
)


def extract_meeting_url(*texts: str | None) -> str | None:
    """Return the first recognizable meeting link found across the given texts."""
    for t in texts:
        if not t:
            continue
        m = _URL_RE.search(t)
        if m:
            return m.group(0).rstrip(").,>")
    return None


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    v = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
