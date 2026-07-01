from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Meeting
from .. import recall

router = APIRouter(prefix="/bots", tags=["bots"])


class InstantBotRequest(BaseModel):
    meeting_url: str


class ScheduledBotRequest(BaseModel):
    meeting_url: str
    join_at: str  # ISO-8601, must be >= 10 minutes in the future


async def _start(meeting_url: str, join_at: str | None, session: AsyncSession):
    bot = await recall.create_bot(meeting_url, join_at=join_at)
    meeting = Meeting(
        recall_bot_id=bot["id"],
        meeting_url=meeting_url,
        status="joining" if join_at is None else "ready",
    )
    session.add(meeting)
    await session.commit()
    await session.refresh(meeting)
    return {"meeting_id": meeting.id, "bot_id": bot["id"], "status": meeting.status}


@router.post("/instant")
async def start_instant_bot(
    body: InstantBotRequest, session: AsyncSession = Depends(get_session)
):
    """Join a meeting happening right now (paste-a-link flow)."""
    return await _start(body.meeting_url, None, session)


@router.post("/schedule")
async def schedule_bot(
    body: ScheduledBotRequest, session: AsyncSession = Depends(get_session)
):
    """Schedule a bot for a future meeting (calendar flow)."""
    return await _start(body.meeting_url, body.join_at, session)
