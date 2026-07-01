"""Routes to connect calendars and trigger sync.

OAuth state is kept in a small in-process dict (fine for a single-user app).
"""
import secrets

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_session
from ..models import CalendarAccount, Meeting
from ..calendar import google, microsoft
from ..calendar.sync import sync_all

router = APIRouter(prefix="/calendars", tags=["calendars"])

_states: set[str] = set()
_UI = "/ui/"


async def _upsert_account(session: AsyncSession, provider: str, tokens: dict):
    existing = (
        await session.execute(
            select(CalendarAccount).where(CalendarAccount.provider == provider)
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = CalendarAccount(provider=provider)
        session.add(existing)
    existing.email = tokens.get("email")
    existing.access_token = tokens["access_token"]
    existing.refresh_token = tokens.get("refresh_token") or existing.refresh_token
    existing.token_expiry = tokens.get("token_expiry")
    await session.commit()


# ---- Google ----------------------------------------------------------------
@router.get("/google/connect")
async def google_connect():
    url, state = google.get_auth_url()
    _states.add(state)
    return RedirectResponse(url)


@router.get("/google/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(None),
    session: AsyncSession = Depends(get_session),
):
    tokens = google.exchange_code(code)
    await _upsert_account(session, "google", tokens)
    _states.discard(state)
    return RedirectResponse(_UI)


# ---- Microsoft -------------------------------------------------------------
@router.get("/microsoft/connect")
async def microsoft_connect():
    state = secrets.token_urlsafe(16)
    _states.add(state)
    return RedirectResponse(microsoft.get_auth_url(state))


@router.get("/microsoft/callback")
async def microsoft_callback(
    code: str = Query(...),
    state: str = Query(None),
    session: AsyncSession = Depends(get_session),
):
    tokens = microsoft.exchange_code(code)
    await _upsert_account(session, "microsoft", tokens)
    _states.discard(state)
    return RedirectResponse(_UI)


# ---- Status / sync ---------------------------------------------------------
@router.get("/status")
async def status(session: AsyncSession = Depends(get_session)):
    accounts = (await session.execute(select(CalendarAccount))).scalars().all()
    return [{"provider": a.provider, "email": a.email} for a in accounts]


@router.post("/sync")
async def sync_now():
    count = await sync_all()
    return {"scheduled": count}


@router.get("/upcoming")
async def upcoming(session: AsyncSession = Depends(get_session)):
    rows = (
        await session.execute(
            select(Meeting)
            .where(Meeting.source != "manual")
            .order_by(Meeting.scheduled_start)
        )
    ).scalars().all()
    return [
        {
            "id": m.id,
            "title": m.title,
            "status": m.status,
            "source": m.source,
            "scheduled_start": m.scheduled_start.isoformat() if m.scheduled_start else None,
        }
        for m in rows
    ]
