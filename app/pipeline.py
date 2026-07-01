"""The post-meeting pipeline: fetch transcript -> summarize -> save -> email.

Called as a background task when the `transcript.done` webhook arrives.
"""
from sqlalchemy import select

from .config import settings
from .db import SessionLocal
from .models import Meeting, MeetingNotes
from . import recall, summarize, emailer


async def process_completed_bot(bot_id: str) -> None:
    async with SessionLocal() as session:
        meeting = (
            await session.execute(
                select(Meeting).where(Meeting.recall_bot_id == bot_id)
            )
        ).scalar_one_or_none()

        if meeting is None:
            return
        if meeting.status == "done":
            return  # idempotent: webhooks can be delivered more than once

        meeting.status = "processing"
        await session.commit()

        # 1. Fetch + flatten transcript
        segments = await recall.get_transcript(bot_id)
        text, lines = recall.flatten_transcript(segments)

        # 2. Summarize
        notes_dict = await summarize.summarize_transcript(text)

        # 3. Persist
        notes = MeetingNotes(
            meeting_id=meeting.id,
            description=notes_dict.get("description"),
            summary=notes_dict.get("summary"),
            agenda=notes_dict.get("agenda"),
            action_items=notes_dict.get("action_items"),
            follow_ups=notes_dict.get("follow_ups"),
            transcript=lines,
        )
        meeting.title = notes_dict.get("title") or meeting.title
        meeting.status = "done"
        session.add(notes)
        await session.commit()

        # 4. Email
        view_url = (
            f"{settings.public_base_url}/meetings/{meeting.id}"
            if settings.public_base_url else None
        )
        await emailer.send_notes_email(notes_dict, view_url)
