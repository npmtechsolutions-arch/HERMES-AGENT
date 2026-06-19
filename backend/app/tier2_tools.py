"""
Tier-2 tools — Calendar (Google) + Email (Gmail), Doc 23 Prompt F. Each is the
Tier-1 contract + a provider call via get_provider_client (auto silent-refresh /
CredentialError on failure). Conditional approval gates new-contact / money /
destructive actions; email.send blocks on a citation mismatch. stdlib urllib only.
"""
import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from .connections import get_provider_client
from .models import KGEntity, MemoryItem, Reminder, now as _now
from .security import ulid
from .tier1_tools import _RE_DATE, _parse_dt, validate_citations
from .tools import ToolResult, TransientError, tool

_CAL_BASE = "https://www.googleapis.com/calendar/v3"
_GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1"


def _api(method, url, token, params=None, body=None):
    """Authenticated provider HTTP (mockable in tests)."""
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        if e.code >= 500:
            raise TransientError(f"provider {e.code}")
        raise ValueError(f"provider error {e.code}")
    except Exception as e:
        raise TransientError(str(e))


def _gcal(method, path, token, params=None, body=None):
    return _api(method, _CAL_BASE + path, token, params, body)


def _gmail(method, path, token, params=None, body=None):
    return _api(method, _GMAIL_BASE + path, token, params, body)


# ── shared guards (ARCHITECTURE §5) ──────────────────────────────────────────
_RE_MONEY = re.compile(r"(₹|\$|€|rs\.?|inr|usd)\s*\d|\b(pay|payment|invoice|amount|transfer|refund|salary|fee)\b", re.I)


def is_known_contact(ctx, attendee) -> bool:
    a = (attendee or "").strip().lower()
    for e in ctx.db.query(KGEntity).filter_by(tenant_id=ctx.actor.tenant_id, type="contact").all():
        if (e.name or "").lower() == a or str((e.attrs or {}).get("email", "")).lower() == a:
            return True
    return False


def mentions_money(text) -> bool:
    return bool(_RE_MONEY.search(text or ""))


# ════════════════════════════ CALENDAR ══════════════════════════════════════
@tool("calendar.list_events", "List calendar events in a time range.",
      {"time_min": {"type": "string", "required": True}, "time_max": {"type": "string", "required": True},
       "calendar_id": {"type": "string", "default": "primary"}}, permission="calendar.read")
def calendar_list_events(ctx, time_min, time_max, calendar_id="primary"):
    cl = get_provider_client(ctx, "google_calendar")
    items = _gcal("GET", f"/calendars/{calendar_id}/events", cl.access_token,
                  params={"timeMin": time_min, "timeMax": time_max,
                          "singleEvents": "true", "orderBy": "startTime"}).get("items", [])
    evs = [{"id": e.get("id"), "title": e.get("summary"),
            "start": e.get("start", {}).get("dateTime"), "end": e.get("end", {}).get("dateTime")}
           for e in items]
    return ToolResult(ok=True, data={"events": evs}, summary=f"You have {len(evs)} event(s) in that range.")


@tool("calendar.find_slots", "Find free slots of a given duration in a window.",
      {"duration_min": {"type": "integer", "required": True},
       "time_min": {"type": "string", "required": True}, "time_max": {"type": "string", "required": True}},
      permission="calendar.read")
def calendar_find_slots(ctx, duration_min, time_min, time_max):
    from datetime import timedelta
    cl = get_provider_client(ctx, "google_calendar")
    items = _gcal("GET", "/calendars/primary/events", cl.access_token,
                  params={"timeMin": time_min, "timeMax": time_max,
                          "singleEvents": "true", "orderBy": "startTime"}).get("items", [])
    busy = sorted((_parse_dt(e.get("start", {}).get("dateTime")), _parse_dt(e.get("end", {}).get("dateTime")))
                  for e in items if e.get("start", {}).get("dateTime") and e.get("end", {}).get("dateTime"))
    cur, end, dur = _parse_dt(time_min), _parse_dt(time_max), timedelta(minutes=int(duration_min))
    slots = []
    for bs, be in busy:
        if bs - cur >= dur:
            slots.append({"start": cur.isoformat(), "end": (cur + dur).isoformat()})
        cur = max(cur, be)
    if end - cur >= dur:
        slots.append({"start": cur.isoformat(), "end": (cur + dur).isoformat()})
    return ToolResult(ok=True, data={"slots": slots[:5]}, summary=f"Found {len(slots[:5])} free slot(s).")


def _create_event_needs_approval(ctx, kw):
    # U6 new-contact gate: approval if inviting anyone not already a known contact
    return any(not is_known_contact(ctx, a) for a in (kw.get("attendees") or []))


@tool("calendar.create_event", "Create a calendar event (approval if inviting a new contact).",
      {"title": {"type": "string", "required": True}, "start": {"type": "string", "required": True},
       "end": {"type": "string", "required": True}, "attendees": {"type": "array"},
       "location": {"type": "string"}},
      permission="calendar.write", approval="conditional", writes_memory=True,
      needs_approval=_create_event_needs_approval)
def calendar_create_event(ctx, title, start, end, attendees=None, location=None):
    cl = get_provider_client(ctx, "google_calendar")
    body = {"summary": title, "start": {"dateTime": start}, "end": {"dateTime": end}}
    if attendees:
        body["attendees"] = [{"email": a} for a in attendees]
    if location:
        body["location"] = location
    ev = _gcal("POST", "/calendars/primary/events", cl.access_token, body=body)
    return ToolResult(ok=True, data={"event_id": ev.get("id"), "link": ev.get("htmlLink")},
                      summary=f"Added “{title}” to your calendar.")


@tool("calendar.update_event", "Update fields on a calendar event.",
      {"id": {"type": "string", "required": True}, "fields": {"type": "object", "required": True}},
      permission="calendar.write", writes_memory=True)
def calendar_update_event(ctx, id, fields):
    cl = get_provider_client(ctx, "google_calendar")
    ev = _gcal("PATCH", f"/calendars/primary/events/{id}", cl.access_token, body=fields)
    return ToolResult(ok=True, data={"event_id": ev.get("id")}, summary="Updated the event.")


def _cancel_event_needs_approval(ctx, kw):
    # destructive gate: approval if the event has attendees (others are affected)
    cl = get_provider_client(ctx, "google_calendar")
    ev = _gcal("GET", f"/calendars/primary/events/{kw['id']}", cl.access_token)
    return bool(ev.get("attendees"))


@tool("calendar.cancel_event", "Cancel a calendar event (approval if it has attendees).",
      {"id": {"type": "string", "required": True}},
      permission="calendar.write", approval="conditional", writes_memory=True,
      needs_approval=_cancel_event_needs_approval)
def calendar_cancel_event(ctx, id):
    cl = get_provider_client(ctx, "google_calendar")
    _gcal("DELETE", f"/calendars/primary/events/{id}", cl.access_token)
    return ToolResult(ok=True, data={"id": id}, summary="Cancelled the event.")


@tool("calendar.book_appointment", "Find a slot and book an appointment.",
      {"with_entity": {"type": "string", "required": True}, "duration_min": {"type": "integer", "default": 30},
       "time_min": {"type": "string", "required": True}, "time_max": {"type": "string", "required": True}},
      permission="calendar.write", writes_memory=True)
def calendar_book_appointment(ctx, with_entity, time_min, time_max, duration_min=30):
    slots = calendar_find_slots(ctx, duration_min, time_min, time_max).data["slots"]
    if not slots:
        return ToolResult(ok=False, error="validation", summary="No free slot in that window.")
    s = slots[0]
    return calendar_create_event(ctx, f"Appointment with {with_entity}", s["start"], s["end"])


# ════════════════════════════ EMAIL ═════════════════════════════════════════
@tool("email.list", "List emails matching a query.",
      {"query": {"type": "string", "default": ""}, "max": {"type": "integer", "default": 10}},
      permission="email.read")
def email_list(ctx, query="", max=10):
    cl = get_provider_client(ctx, "gmail")
    msgs = _gmail("GET", "/users/me/messages", cl.access_token,
                  params={"q": query, "maxResults": int(max)}).get("messages", [])
    return ToolResult(ok=True, data={"messages": msgs}, summary=f"Found {len(msgs)} email(s).")


@tool("email.read", "Read an email by id.", {"id": {"type": "string", "required": True}},
      permission="email.read")
def email_read(ctx, id):
    cl = get_provider_client(ctx, "gmail")
    m = _gmail("GET", f"/users/me/messages/{id}", cl.access_token)
    return ToolResult(ok=True, data={"snippet": m.get("snippet"), "id": id}, summary="Opened the email.")


@tool("email.draft", "Draft an email — does not send.",
      {"to": {"type": "string", "required": True}, "subject": {"type": "string", "required": True},
       "body": {"type": "string", "required": True}, "source": {"type": "string"}},
      permission="email.draft", writes_memory=True)
def email_draft(ctx, to, subject, body, source=None):
    m = MemoryItem(id=ulid("mem"), tenant_id=ctx.actor.tenant_id, memory_class="personal",
                   title=subject, source_type="email_draft",
                   body=json.dumps({"to": to, "subject": subject, "body": body, "source": source}),
                   tier="hot", confidence=1.0)
    ctx.db.add(m); ctx.db.flush()
    return ToolResult(ok=True, data={"draft_id": m.id, "to": to},
                      summary=f"Drafted an email to {to} (review before sending).")


def _load_draft(ctx, draft_id):
    m = ctx.db.get(MemoryItem, draft_id)
    return json.loads(m.body) if (m and m.source_type == "email_draft") else None


def _email_send_needs_approval(ctx, kw):
    d = _load_draft(ctx, kw.get("draft_id", ""))
    if not d:
        return True
    return (not is_known_contact(ctx, d.get("to", ""))) or mentions_money(d.get("body", ""))   # U5/U6


@tool("email.send", "Send a previously drafted email.",
      {"draft_id": {"type": "string", "required": True}},
      permission="email.send", approval="conditional", writes_memory=True,
      needs_approval=_email_send_needs_approval)
def email_send(ctx, draft_id):
    d = _load_draft(ctx, draft_id)
    if not d:
        return ToolResult(ok=False, error="validation", summary="That draft doesn't exist.")
    # source-cited figures: block if a figure/date in the body isn't in the source (U4/§5)
    if d.get("source"):
        bad = validate_citations(d.get("body", ""), d["source"])
        if bad:
            return ToolResult(ok=False, error="validation",
                              summary=f"Blocked: “{bad}” isn't in the source — not sending (source-cited figures only).")
    cl = get_provider_client(ctx, "gmail")
    raw = base64.urlsafe_b64encode(
        f"To: {d['to']}\r\nSubject: {d['subject']}\r\n\r\n{d['body']}".encode()).decode()
    msg = _gmail("POST", "/users/me/messages/send", cl.access_token, body={"raw": raw})
    return ToolResult(ok=True, data={"message_id": msg.get("id")}, summary=f"Sent your email to {d['to']}.")


@tool("email.detect_bills", "Scan recent emails for due dates → track them as deadlines.",
      {"query": {"type": "string", "default": "invoice OR bill OR due OR payment"},
       "max": {"type": "integer", "default": 20}},
      permission="email.read", writes_memory=True)
def email_detect_bills(ctx, query="invoice OR bill OR due OR payment", max=20):
    cl = get_provider_client(ctx, "gmail")
    msgs = _gmail("GET", "/users/me/messages", cl.access_token,
                  params={"q": query, "maxResults": int(max)}).get("messages", [])
    found = []
    for m in msgs:
        full = _gmail("GET", f"/users/me/messages/{m['id']}", cl.access_token)
        text = full.get("snippet", "")
        d = _RE_DATE.search(text)
        if d and _parse_dt(d.group()):
            label = (text[:40] or "Bill").strip()
            ctx.db.add(Reminder(id=ulid("rem"), tenant_id=ctx.actor.tenant_id, user_id=ctx.actor.user_id,
                                text=label, due_at=_parse_dt(d.group()), kind="deadline",
                                detail="bill", status="active"))
            found.append(label)
    ctx.db.flush()
    return ToolResult(ok=True, data={"bills": found},
                      summary=f"Found {len(found)} bill(s) with due dates — tracked them for you.")
