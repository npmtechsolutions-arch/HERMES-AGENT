"""
Ask-Your-Business — the chat-based dashboard. Per the dashboard strategy:
"Don't build a custom dashboard. The agent itself is the dashboard." The user
asks a plain-language question ("how many leads today?", "what's my no-show
rate?", "set a daily summary at 8am") and gets a real, computed answer from
their own data — no charts to wire up, no BI tool.

This is Phase 1 (Day-1) of the dashboard plan: chat answers. Phase 2 (Telegram
bot) and Phase 3 (web dashboard) reuse these same metric resolvers.
"""
import re
from datetime import timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Principal, current_user
from ..models import (Approval, CommMessage, CommThread, Lead, RoiEntry,
                      Schedule, SiteVisit, Task, Workflow, now)
from ..security import ulid

router = APIRouter(tags=["ask"])


# ── time-window parsing ──────────────────────────────────────────────────────
def _window(text):
    """Return (since, label) for the period mentioned in the question."""
    t = text.lower()
    n = now()
    if "yesterday" in t:
        return n - timedelta(days=2), n - timedelta(days=1), "yesterday"
    if "this month" in t or "month" in t:
        return n - timedelta(days=30), n, "this month"
    if "this week" in t or "week" in t or "7 day" in t:
        return n - timedelta(days=7), n, "this week"
    if "today" in t or "so far" in t:
        return n - timedelta(days=1), n, "today"
    return n - timedelta(days=7), n, "this week"   # sensible default


def _in(dt, lo, hi):
    return dt is not None and lo <= dt <= hi


# ── metric resolvers: each returns (answer, value, data) ─────────────────────
def m_leads(db, tid, text):
    lo, hi, lbl = _window(text)
    leads = db.query(Lead).filter_by(tenant_id=tid).all()
    n = sum(1 for l in leads if _in(l.created_at, lo, hi))
    hot = sum(1 for l in leads if _in(l.created_at, lo, hi) and l.score == "hot")
    return (f"You got {n} new lead{'s' if n != 1 else ''} {lbl}"
            + (f", {hot} of them hot." if hot else "."), n,
            {"new": n, "hot": hot, "period": lbl})


def m_appointments(db, tid, text):
    lo, hi, lbl = _window(text)
    vs = db.query(SiteVisit).filter_by(tenant_id=tid).all()
    upcoming = [v for v in vs if v.slot and v.slot >= now()
                and v.status in ("offered", "confirmed", "reminded")]
    in_win = sum(1 for v in vs if _in(v.slot, lo, hi))
    nxt = min((v.slot for v in upcoming), default=None)
    ans = f"You have {in_win} appointment{'s' if in_win != 1 else ''} {lbl}."
    if nxt:
        ans += f" Next one is {nxt.strftime('%a %d %b, %H:%M')}."
    return ans, in_win, {"in_window": in_win, "upcoming": len(upcoming), "period": lbl}


def m_noshow(db, tid, text):
    vs = db.query(SiteVisit).filter_by(tenant_id=tid).all()
    finished = [v for v in vs if v.status in ("done", "no_show")]
    ns = sum(1 for v in finished if v.status == "no_show")
    total = len(finished)
    rate = round(100 * ns / total) if total else 0
    if not total:
        return "No appointments have finished yet, so there's no no-show rate to report.", 0, {"rate": 0}
    return (f"Your no-show rate is {rate}% — {ns} of {total} finished appointments. "
            + ("That's healthy." if rate <= 10 else "Worth turning on no-show reminders."),
            rate, {"rate": rate, "no_shows": ns, "finished": total})


def m_messages(db, tid, text):
    lo, hi, lbl = _window(text)
    threads = {t.id for t in db.query(CommThread).filter_by(tenant_id=tid).all()}
    msgs = db.query(CommMessage).filter(CommMessage.thread_id.in_(threads or {""})).all()
    out = sum(1 for m in msgs if m.direction == "out" and _in(m.sent_at, lo, hi))
    return f"{out} message{'s' if out != 1 else ''} sent {lbl}.", out, {"sent": out, "period": lbl}


def m_tasks(db, tid, text):
    lo, hi, lbl = _window(text)
    tasks = db.query(Task).filter_by(tenant_id=tid).all()
    done = sum(1 for t in tasks if t.status == "done")
    open_ = sum(1 for t in tasks if t.status in ("queued", "running", "blocked"))
    return (f"{done} task{'s' if done != 1 else ''} completed, {open_} still open.",
            done, {"done": done, "open": open_})


def m_hours(db, tid, text):
    lo, hi, lbl = _window(text)
    roi = [r for r in db.query(RoiEntry).filter_by(tenant_id=tid).all() if _in(r.at, lo, hi)]
    mins = sum(float(r.value_minutes or 0) for r in roi)
    hrs = round(mins / 60, 1)
    after = sum(1 for r in roi if r.after_hours)
    return (f"Your agents saved about {hrs} staff-hour{'s' if hrs != 1 else ''} {lbl}"
            + (f", with {after} action{'s' if after != 1 else ''} handled after-hours." if after else "."),
            hrs, {"hours_saved": hrs, "actions": len(roi), "after_hours": after, "period": lbl})


def m_approvals(db, tid, text):
    n = db.query(Approval).filter_by(tenant_id=tid, state="pending").count()
    if not n:
        return "Nothing is waiting for your approval — you're all clear.", 0, {"pending": 0}
    return f"{n} approval{'s' if n != 1 else ''} {'are' if n != 1 else 'is'} waiting on you.", n, {"pending": n}


def m_pipeline(db, tid, text):
    leads = db.query(Lead).filter_by(tenant_id=tid).all()
    by = {}
    for l in leads:
        by[l.stage] = by.get(l.stage, 0) + 1
    won = by.get("won", 0)
    closed = won + by.get("lost", 0)
    conv = round(100 * won / closed) if closed else 0
    parts = ", ".join(f"{v} {k}" for k, v in sorted(by.items(), key=lambda x: -x[1]))
    return (f"Pipeline: {parts or 'empty'}." + (f" Conversion is {conv}%." if closed else ""),
            len(leads), {"by_stage": by, "conversion_pct": conv})


# ── schedule a recurring summary ("send me a daily summary at 8am") ──────────
def m_schedule(db, tid, text):
    m = re.search(r"\b(\d{1,2})\s*(?::(\d{2}))?\s*(am|pm)\b", text.lower())
    hour, minute = 8, 0
    if m:
        hour = int(m.group(1)) % 12 + (12 if m.group(3) == "pm" else 0)
        minute = int(m.group(2) or 0)
    expr = f"{minute} {hour} * * *"
    wf = db.query(Workflow).filter_by(tenant_id=tid, name="Daily summary").first()
    if not wf:
        wf = Workflow(id=ulid("wfl"), tenant_id=tid, name="Daily summary", status="active",
                      source_utterance="Send me a daily business summary",
                      graph={"nodes": [{"id": "briefing", "type": "daily_briefing"}], "edges": []})
        db.add(wf)
        db.flush()
    sch = db.query(Schedule).filter_by(tenant_id=tid, workflow_id=wf.id).first()
    if not sch:
        sch = Schedule(id=ulid("sch"), tenant_id=tid, workflow_id=wf.id, kind="cron")
        db.add(sch)
    sch.expression = expr
    db.commit()
    when = f"{hour % 12 or 12}:{minute:02d} {'am' if hour < 12 else 'pm'}"
    return (f"Done — I'll send you a daily business summary every day at {when}.",
            1, {"schedule": expr, "time": when})


# question → resolver (first match wins; order matters — specific before general)
ROUTES = [
    (r"daily (summary|briefing|report)|summary at|every (morning|day)|remind me", m_schedule),
    (r"no.?show|didn.?t show|missed appoint", m_noshow),
    (r"appointment|visit|booking|meeting|schedule(d)? for", m_appointments),
    (r"lead|inquir|enquir|prospect", m_leads),
    (r"message|sms|whatsapp|sent|reply|replies", m_messages),
    (r"task|to.?do|completed", m_tasks),
    (r"hour|time saved|roi|productiv|saved", m_hours),
    (r"approval|waiting|pending|sign.?off", m_approvals),
    (r"pipeline|conversion|convert|stage|won|lost|funnel", m_pipeline),
]

SUGGESTIONS = [
    "How many leads did I get today?",
    "Show me this week's appointments",
    "What's my no-show rate?",
    "How many staff-hours did my agents save this week?",
    "What's my pipeline conversion?",
    "Send me a daily summary at 8am",
]


class AskIn(BaseModel):
    question: str


@router.post("/ask")
def ask(body: AskIn, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """The chat-based dashboard: a plain-language question → a real, computed answer."""
    text = (body.question or "").strip()
    for pattern, fn in ROUTES:
        if re.search(pattern, text.lower()):
            answer, value, data = fn(db, p.tenant_id, text)
            return {"answer": answer, "value": value, "data": data,
                    "metric": fn.__name__[2:], "understood": True}
    return {"answer": "I can answer questions about your leads, appointments, no-shows, "
                      "messages, tasks, hours saved, approvals and pipeline — just ask.",
            "value": None, "data": {}, "metric": None, "understood": False,
            "suggestions": SUGGESTIONS}


@router.get("/ask/suggestions")
def suggestions(p: Principal = Depends(current_user)):
    """Starter questions for the chat dashboard."""
    return {"suggestions": SUGGESTIONS}
