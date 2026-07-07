"""Turn a meeting recording into structured notes using Gemini.

Two functions:
  - transcribe_media(url, mime_type)  → raw transcript text (Gemini multimodal)
  - summarize_transcript(text)        → structured notes dict
"""
import json
import httpx

from google import genai
from google.genai import types

from .config import settings

SUMMARY_PROMPT = """You are a meeting assistant. Given the transcript below, return ONLY
a JSON object (no markdown, no backticks) with this exact shape:

{{
  "title": "short meeting title",
  "description": "2-4 sentence description of what the meeting was about",
  "summary": "a clear narrative recap of the discussion",
  "agenda": [{{"topic": "...", "t_start": "mm:ss or null"}}],
  "action_items": [{{"owner": "name or null", "task": "...", "due": "date or null"}}],
  "follow_ups": ["open question or next step", "..."]
}}

Transcript:
---
{transcript}
---
"""

TRANSCRIBE_PROMPT = (
    "Transcribe this meeting audio in full. "
    "Format each line as: SpeakerName: sentence. "
    "If you cannot identify the speaker write 'Unknown'. "
    "Return only the transcript, no extra commentary."
)


def _strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1] if "```" in s else s
        s = s.replace("json", "", 1).strip()
        if s.endswith("```"):
            s = s[:-3].strip()
    return s


async def transcribe_media(media_url: str, mime_type: str = "video/mp4") -> str:
    """Download the recording from Recall and transcribe with Gemini."""
    async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
        resp = await client.get(media_url)
        resp.raise_for_status()
        media_bytes = resp.content

    print(f"[summarize] downloaded {len(media_bytes)//1024}KB mime={mime_type}")

    ai = genai.Client(api_key=settings.gemini_api_key)

    # Gemini inline limit is ~20MB; use the File API for anything larger
    if len(media_bytes) > 18 * 1024 * 1024:
        import io
        uploaded = await ai.aio.files.upload(
            file=io.BytesIO(media_bytes),
            config=types.UploadFileConfig(mime_type=mime_type, display_name="meeting"),
        )
        contents = [uploaded, TRANSCRIBE_PROMPT]
    else:
        contents = [
            types.Part.from_bytes(data=media_bytes, mime_type=mime_type),
            TRANSCRIBE_PROMPT,
        ]

    response = await ai.aio.models.generate_content(
        model=settings.gemini_model,
        contents=contents,
    )
    return (response.text or "").strip()


async def summarize_transcript(text: str) -> dict:
    client = genai.Client(api_key=settings.gemini_api_key)
    resp = await client.aio.models.generate_content(
        model=settings.gemini_model,
        contents=SUMMARY_PROMPT.format(transcript=text[:200_000]),
    )
    raw = _strip_fences(resp.text or "{}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "title": "Meeting",
            "description": None,
            "summary": raw,
            "agenda": [],
            "action_items": [],
            "follow_ups": [],
        }
