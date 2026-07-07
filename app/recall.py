"""Thin wrapper around the Recall.ai REST API.

Docs: https://docs.recall.ai/reference/bot_create
"""
import httpx

from .config import settings


def _headers() -> dict:
    return {
        "Authorization": f"Token {settings.recall_api_key}",
        "Content-Type": "application/json",
    }


async def create_bot(meeting_url: str, join_at: str | None = None) -> dict:
    """Send a bot to a meeting.

    - Omit `join_at` for an ad-hoc bot (join a meeting happening now).
    - Pass an ISO-8601 `join_at` (>= 10 min in the future) to schedule one.
    """
    payload: dict = {
        "meeting_url": meeting_url,
        "bot_name": settings.bot_name,
        "output_media": {
            "audio": {"format": "mp3"},
        },
    }
    if join_at:
        payload["join_at"] = join_at

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{settings.recall_base_url}/bot",
            headers=_headers(),
            json=payload,
        )
        r.raise_for_status()
        return r.json()


async def get_bot(bot_id: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{settings.recall_base_url}/bot/{bot_id}",
            headers=_headers(),
        )
        r.raise_for_status()
        return r.json()


async def get_recording_url(bot_id: str) -> tuple[str, str] | tuple[None, None]:
    """Return (download_url, mime_type) for the bot recording, or (None, None)."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{settings.recall_base_url}/bot/{bot_id}",
            headers=_headers(),
        )
        r.raise_for_status()
        data = r.json()

    for rec in data.get("recordings") or []:
        shortcuts = rec.get("media_shortcuts") or {}

        # Prefer audio (smaller file) — only present if workspace enables it
        audio = shortcuts.get("audio_mixed")
        if isinstance(audio, dict):
            url = (audio.get("data") or {}).get("download_url")
            if url:
                return url, "audio/mp3"

        # Fall back to video (mp4) — Recall records this by default
        video = shortcuts.get("video_mixed")
        if isinstance(video, dict):
            url = (video.get("data") or {}).get("download_url")
            if url:
                return url, "video/mp4"

    return None, None


async def get_transcript(bot_id: str) -> list:
    """Returns a list of transcript segments; each has `speaker` and `words[]`."""
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(
            f"{settings.recall_base_url}/bot/{bot_id}/transcript",
            headers=_headers(),
        )
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("results", "transcript", "data", "segments"):
                if isinstance(data.get(key), list):
                    return data[key]
        return []


def flatten_transcript(segments: list) -> tuple[str, list]:
    """Turn raw Recall segments into (plain_text, structured_lines)."""
    lines = []
    text_parts = []
    for seg in segments:
        speaker = seg.get("speaker") or "Unknown"
        words = seg.get("words") or []
        text = " ".join(w.get("text", "") for w in words).strip()
        if not text:
            continue
        start = words[0].get("start_timestamp") if words else None
        lines.append({"speaker": speaker, "t": start, "text": text})
        text_parts.append(f"{speaker}: {text}")
    return "\n".join(text_parts), lines
