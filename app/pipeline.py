"""Post-meeting pipeline: get recording → transcribe → summarize → save → email."""
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
        if meeting.status in ("done", "processing"):
            return  # already handled or in-flight

        meeting.status = "processing"
        await session.commit()

        try:
            # 1. Get recording URL + mime type from Recall bot object
            media_url, mime_type = await recall.get_recording_url(bot_id)
            print(f"[pipeline] media_url={media_url} mime={mime_type}")

            if not media_url:
                print(f"[pipeline] No recording for bot {bot_id} — marking done.")
                meeting.status = "done"
                await session.commit()
                return

            # 2. Transcribe with Gemini
            text = await summarize.transcribe_media(media_url, mime_type)
            if not text.strip():
                print(f"[pipeline] Empty transcript for bot {bot_id} — marking done.")
                meeting.status = "done"
                await session.commit()
                return

            # Build structured lines for storage
            lines = []
            for line in text.splitlines():
                if ":" in line:
                    speaker, _, body = line.partition(":")
                    lines.append({"speaker": speaker.strip(), "t": None, "text": body.strip()})
                elif line.strip():
                    lines.append({"speaker": "Unknown", "t": None, "text": line.strip()})

            # 3. Summarize
            notes_dict = await summarize.summarize_transcript(text)

            # 4. Persist notes — do this before email so notes are never lost
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

            # 5. Email — failure here must NOT roll back the meeting status
            view_url = (
                f"{settings.public_base_url}/meetings/{meeting.id}"
                if settings.public_base_url else None
            )
            try:
                await emailer.send_notes_email(notes_dict, view_url)
            except Exception as email_err:
                print(f"[pipeline] Email failed (notes still saved): {email_err}")

        except Exception as exc:
            print(f"[pipeline] ERROR for bot {bot_id}: {exc}")
            meeting.status = "failed"
            await session.commit()
            raise
