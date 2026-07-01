"""Thin wrapper around the Recall.ai REST API.

Docs: https://docs.recall.ai/reference/bot_create
"""
import httpx

from .config import settings


def _headers() -> dict:
    print("RECALL KEY =", settings.recall_api_key)

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
    }
    # payload: dict = {
    #     "meeting_url": meeting_url,
    #     "bot_name": settings.bot_name,
    #     # `meeting_captions` is the simplest transcription option to start with.
    #     # Swap to a provider (e.g. assembly_ai) for higher quality later.
    #     "transcription_options": {"provider": "meeting_captions"},
    # }
    if join_at:
        payload["join_at"] = join_at

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{settings.recall_base_url}/bot",
            headers=_headers(),
            json=payload,
        )

        print("===== DEBUG =====")
        print("URL:", f"{settings.recall_base_url}/bot")
        print("API KEY:", settings.recall_api_key)
        print("PAYLOAD:", payload)
        print("STATUS:", r.status_code)
        print("BODY:", r.text)
        print("=================")

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
    
    # async with httpx.AsyncClient(timeout=30) as client:
    #     r = await client.get(
    #         f"{settings.recall_base_url}/bot/{bot_id}",
    #         headers=_headers(),
    #     )
    #     r.raise_for_status()
    #     return r.json()


async def get_transcript(bot_id: str) -> list:
    """Returns a list of segments: each has `speaker` and `words[]`."""
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(
            f"{settings.recall_base_url}/bot/{bot_id}/transcript",
            headers=_headers(),
        )
        r.raise_for_status()
        return r.json()


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
