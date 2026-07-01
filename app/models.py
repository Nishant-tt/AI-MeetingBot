import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    recall_bot_id: Mapped[str | None] = mapped_column(String, index=True, default=None)
    meeting_url: Mapped[str] = mapped_column(String)
    title: Mapped[str | None] = mapped_column(String, default=None)
    # ready | joining | in_call | processing | done | failed
    status: Mapped[str] = mapped_column(String, default="ready")

    # provenance: how this meeting got scheduled
    source: Mapped[str] = mapped_column(String, default="manual")  # manual|google|microsoft
    external_event_id: Mapped[str | None] = mapped_column(String, index=True, default=None)
    scheduled_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    notes: Mapped["MeetingNotes | None"] = relationship(
        back_populates="meeting", uselist=False
    )


class MeetingNotes(Base):
    __tablename__ = "meeting_notes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id"), index=True)

    description: Mapped[str | None] = mapped_column(Text, default=None)
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    agenda: Mapped[list | None] = mapped_column(JSON, default=None)
    action_items: Mapped[list | None] = mapped_column(JSON, default=None)
    follow_ups: Mapped[list | None] = mapped_column(JSON, default=None)
    transcript: Mapped[list | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    meeting: Mapped["Meeting"] = relationship(back_populates="notes")


class CalendarAccount(Base):
    __tablename__ = "calendar_accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    provider: Mapped[str] = mapped_column(String)  # google | microsoft
    email: Mapped[str | None] = mapped_column(String, default=None)
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str | None] = mapped_column(Text, default=None)
    token_expiry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
