# Meeting Notetaker (single-user)

A FastAPI backend + lightweight web UI. You either **paste a meeting link** or
**connect a calendar**; a Recall.ai bot joins the meeting, and when it ends the
app fetches the transcript, generates **notes / agenda / summary / follow-ups**
with an LLM, saves them, shows them in the UI, and emails them to you.

```
Paste link ─▶ /bots/instant ─┐
                             ├─▶ Recall bot joins ─▶ meeting ends
Calendar  ─▶ auto-schedule ──┘                          │
                                          webhook: transcript.done
                                                        │
                          fetch transcript ─▶ summarize ─▶ save ─▶ email
                                                        │
                                   UI: http://localhost:8000/ui/
```

## 1. Setup
```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                  # fill in keys (see below)
```

Minimum to start: `RECALL_API_KEY` and `GEMINI_API_KEY`. Calendars and email
can stay blank — those features just stay off until configured.

## 2. Run
```bash
uvicorn app.main:app --reload --port 8000
```
Open the UI at **http://localhost:8000/ui/**

In a second terminal, expose the server so Recall can reach your webhook:
```bash
ngrok http 8000
# put the https URL in PUBLIC_BASE_URL in .env, restart uvicorn
```

## 3. Recall webhook
Dashboard → https://us-west-2.recall.ai/dashboard/webhooks → add
`<PUBLIC_BASE_URL>/webhooks/recall` and subscribe to:
`bot.done`, `recording.done`, `recording.failed`, `transcript.done`, `transcript.failed`.

## 4. Calendars (optional)
**Google:** Google Cloud Console → OAuth Client ID (Web) → redirect
`http://localhost:8000/calendars/google/callback`; enable Calendar API; put
`GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` in `.env`.

**Outlook:** Azure Portal → App registration → redirect
`http://localhost:8000/calendars/microsoft/callback`; delegated permissions
`Calendars.Read`, `User.Read`, `offline_access`; add a client secret; put
`MS_CLIENT_ID` / `MS_CLIENT_SECRET` in `.env`.

Then click **Connect Google / Connect Outlook** in the UI. A background job
(every `CALENDAR_SYNC_MINUTES`) scans the next `CALENDAR_WINDOW_HOURS` and
schedules a bot per meeting that has a join link. Each event is scheduled once.

## What's where
```
app/
  main.py            app + /meetings + serves the UI
  config.py          env settings
  recall.py          Recall API client + transcript flattening
  summarize.py       LLM -> structured notes (swap for your gateway here)
  emailer.py         emails the notes
  pipeline.py        fetch -> summarize -> save -> email (idempotent)
  scheduler.py       periodic calendar sync (APScheduler)
  db.py / models.py  Meeting, MeetingNotes, CalendarAccount
  routers/
    bots.py          POST /bots/instant  &  /bots/schedule
    webhooks.py      POST /webhooks/recall
    calendars.py     connect / callback / status / sync / upcoming
  calendar/
    google.py        Google OAuth + upcoming events
    microsoft.py     Outlook OAuth + upcoming events (Graph)
    extract.py       pull a meeting link out of event text
    sync.py          schedule bots for new events
frontend/index.html  paste-link screen, calendar connect, meeting + notes view
```

## Before production
- **Harden webhook verification** (`routers/webhooks.py` is a dev stub — Recall uses Svix).
- **Swap SQLite → Postgres** (`DATABASE_URL`) and use Alembic migrations.
- **Encrypt stored OAuth tokens** (they're plaintext in the DB right now).
- **Tighten CORS / OAuth state handling** for a real deployment.
