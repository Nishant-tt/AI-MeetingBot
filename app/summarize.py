"""Turn a transcript into structured notes.

This is intentionally isolated so you can point it at your own LLM gateway
later instead of calling Gemini directly. The contract is one function:

    async def summarize_transcript(text: str) -> dict
"""
import json

from google import genai

from .config import settings

PROMPT = """You are a meeting assistant. Given the transcript below, return ONLY
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


def _strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1] if "```" in s else s
        s = s.replace("json", "", 1).strip()
        if s.endswith("```"):
            s = s[: -3].strip()
    return s


async def summarize_transcript(text: str) -> dict:
    client = genai.Client(api_key=settings.gemini_api_key)
    resp = await client.aio.models.generate_content(
        model=settings.gemini_model,
        contents=PROMPT.format(transcript=text[:200_000]),
    )
    raw = _strip_fences(resp.text or "{}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fail soft: keep the raw output so nothing is lost.
        return {
            "title": "Meeting",
            "description": None,
            "summary": raw,
            "agenda": [],
            "action_items": [],
            "follow_ups": [],
        }
