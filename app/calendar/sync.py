"""Scan connected calendars and schedule a bot for each upcoming meeting.

Runs on a timer (see app/scheduler.py) and can also be triggered on demand.
Idempotent: a meeting is only scheduled once, keyed by external_event_id.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .. import recall
from ..config import settings
from ..db import SessionLocal
from ..models import CalendarAccount, Meeting
from . import google, microsoft

_PROVIDERS = {"google": google, "microsoft": microsoft}


async def sync_all() -> int:
    """Schedule bots for new upcoming meetings. Returns count newly scheduled."""
    scheduled = 0
    async with SessionLocal() as session:
        accounts = (await session.execute(select(CalendarAccount))).scalars().all()

        for account in accounts:
            provider = _PROVIDERS.get(account.provider)
            if provider is None:
                continue
            try:
                events = await asyncio.to_thread(provider.list_upcoming, account)
            except Exception as exc:  # keep one bad account from breaking the rest
                print(f"[calendar-sync] {account.provider} failed: {exc}")
                continue

            for ev in events:
                exists = (
                    await session.execute(
                        select(Meeting).where(
                            Meeting.external_event_id == ev["event_id"]
                        )
                    )
                ).scalar_one_or_none()
                if exists:
                    continue

                start: datetime = ev["start"]
                now = datetime.now(timezone.utc)
                # Recall needs join_at >= ~10 min ahead; closer than that -> ad-hoc.
                join_at = (
                    None if start <= now + timedelta(minutes=11) else start.isoformat()
                )
                try:
                    bot = await recall.create_bot(ev["meeting_url"], join_at=join_at)
                except Exception as exc:
                    print(f"[calendar-sync] create_bot failed: {exc}")
                    continue

                session.add(Meeting(
                    recall_bot_id=bot["id"],
                    meeting_url=ev["meeting_url"],
                    title=ev["title"],
                    status="ready",
                    source=account.provider,
                    external_event_id=ev["event_id"],
                    scheduled_start=start,
                ))
                scheduled += 1

        await session.commit()
    return scheduled
