import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from .db import init_db, get_session
from .models import Meeting
from .routers import bots, webhooks, calendars
from .scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Meeting Notetaker", lifespan=lifespan)

# Dev convenience: allow the frontend to call the API if served separately.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bots.router)
app.include_router(webhooks.router)
app.include_router(calendars.router)

@app.get("/")
def root():
    return {"message": "hello"}

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/meetings")
async def list_meetings(session: AsyncSession = Depends(get_session)):
    rows = (
        await session.execute(select(Meeting).order_by(Meeting.created_at.desc()))
    ).scalars().all()
    return [
        {
            "id": m.id,
            "title": m.title or "Untitled meeting",
            "status": m.status,
            "source": m.source,
            "created_at": m.created_at.isoformat(),
        }
        for m in rows
    ]


@app.get("/meetings/{meeting_id}")
async def get_meeting(meeting_id: str, session: AsyncSession = Depends(get_session)):
    meeting = (
        await session.execute(
            select(Meeting)
            .where(Meeting.id == meeting_id)
            .options(selectinload(Meeting.notes))
        )
    ).scalar_one_or_none()

    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")

    n = meeting.notes
    return {
        "id": meeting.id,
        "title": meeting.title,
        "status": meeting.status,
        "meeting_url": meeting.meeting_url,
        "notes": None if n is None else {
            "description": n.description,
            "summary": n.summary,
            "agenda": n.agenda,
            "action_items": n.action_items,
            "follow_ups": n.follow_ups,
            "transcript": n.transcript,
        },
    }


# Serve the static frontend at /ui (after API routes so it doesn't shadow them).
_frontend = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.isdir(_frontend):
    app.mount("/ui", StaticFiles(directory=_frontend, html=True), name="ui")
