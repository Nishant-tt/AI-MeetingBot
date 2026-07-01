"""Send meeting notes by email over SMTP (stdlib, run in a thread)."""
import asyncio
import smtplib
from email.mime.text import MIMEText

from .config import settings


def _render_html(notes: dict, view_url: str | None) -> str:
    def li(items, fmt):
        return "".join(f"<li>{fmt(x)}</li>" for x in (items or []))

    agenda = li(notes.get("agenda"), lambda x: f"{x.get('topic','')} "
                                               f"<i>{x.get('t_start') or ''}</i>")
    actions = li(notes.get("action_items"),
                 lambda x: f"<b>{x.get('owner') or '—'}</b>: {x.get('task','')} "
                           f"<i>{x.get('due') or ''}</i>")
    follow = li(notes.get("follow_ups"), lambda x: x)

    link = f'<p><a href="{view_url}">View full transcript &amp; notes</a></p>' \
        if view_url else ""

    return f"""
    <h2>{notes.get('title', 'Meeting notes')}</h2>
    <p>{notes.get('description') or ''}</p>
    <h3>Summary</h3>
    <p>{notes.get('summary') or ''}</p>
    <h3>Agenda</h3><ul>{agenda}</ul>
    <h3>Action items</h3><ul>{actions}</ul>
    <h3>Follow-ups</h3><ul>{follow}</ul>
    {link}
    """


def _send_sync(subject: str, html: str) -> None:
    msg = MIMEText(html, "html")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_user
    msg["To"] = settings.notify_email

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)


async def send_notes_email(notes: dict, view_url: str | None = None) -> None:
    if not settings.smtp_host or not settings.notify_email:
        return  # email not configured; skip silently in dev
    subject = f"Meeting notes: {notes.get('title', 'Meeting')}"
    html = _render_html(notes, view_url)
    await asyncio.to_thread(_send_sync, subject, html)
