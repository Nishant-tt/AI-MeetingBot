"""Receives Recall.ai webhook events.

IMPORTANT (production): verify the webhook signature before trusting the body.
Recall uses Svix-style signed webhooks. The simplest hardening is:

    pip install svix
    from svix.webhooks import Webhook
    Webhook(settings.recall_webhook_secret).verify(raw_body, dict(request.headers))

Confirm the exact scheme in Recall's webhook docs (or via their docs MCP).
Until then, keep your ngrok/webhook URL secret and treat this as dev-only.
"""
from fastapi import APIRouter, Request, BackgroundTasks

from ..pipeline import process_completed_bot

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _verify(raw_body: bytes, headers) -> bool:
    # TODO: implement Svix verification (see module docstring). Dev stub: allow.
    return True


@router.post("/recall")
async def recall_webhook(request: Request, background: BackgroundTasks):
    raw = await request.body()
    if not _verify(raw, request.headers):
        return {"ok": False}

    event = await request.json()
    event_type = event.get("event")

    # Recall delivers the bot id under data.bot.id (shape can vary by event);
    # this digs it out defensively.
    data = event.get("data", {})
    bot_id = (
        data.get("bot", {}).get("id")
        or data.get("bot_id")
        or data.get("id")
    )

    # Kick off processing once the transcript is ready. Return 2xx immediately;
    # do the heavy lifting in the background so Recall doesn't retry.
    if event_type in ("transcript.done", "bot.done") and bot_id:
        background.add_task(process_completed_bot, bot_id)

    return {"ok": True}
