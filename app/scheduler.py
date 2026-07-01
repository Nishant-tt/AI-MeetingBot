"""Periodic calendar sync using APScheduler (async)."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import settings
from .calendar.sync import sync_all

_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        sync_all,
        "interval",
        minutes=settings.calendar_sync_minutes,
        id="calendar_sync",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
