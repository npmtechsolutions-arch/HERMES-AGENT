"""
Tier-2 tools — Calendar (Google) + Email (Gmail), Doc 23 Prompt F. Each is the
Tier-1 contract + a provider call via get_provider_client (auto silent-refresh /
CredentialError on failure). Conditional approval gates new-contact / money /
destructive actions; email.send blocks on a citation mismatch. stdlib urllib only.
"""
import base64
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from .connections import get_provider_client
from .events import hub
from .models import KGEntity, MemoryItem, Reminder, WhatsAppOutbox, now as _now
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


# ════════════════════════════ WHATSAPP (Doc 23 Prompt G) ════════════════════
# Provider HTTP (mockable). _wa_post returns a STATUS so the tool can queue on a
# rate-limit instead of letting the wrapper's transient-retry handle it.
def _wa_phone_id():
    return os.getenv("HERMUS_WA_PHONE_ID", "")


def _wa_post(token, phone_id, payload):
    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return "sent", json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return "rate_limited", None
        if e.code >= 500:
            raise TransientError(f"provider {e.code}")
        raise ValueError(f"provider error {e.code}")
    except Exception as e:
        raise TransientError(str(e))


def _wa_incoming(token, since):
    return []   # real: pulled from the webhook store; mocked in tests


def _wa_quality(token, phone_id):
    return "GREEN"   # real: WhatsApp Business quality_rating; mocked in tests


# 24-hour customer-service window — tracked on the contact's KG entity.
def _find_contact(ctx, who):
    w = (who or "").strip().lower()
    for e in ctx.db.query(KGEntity).filter_by(tenant_id=ctx.actor.tenant_id, type="contact").all():
        a = e.attrs or {}
        if (e.name or "").lower() == w or str(a.get("phone", "")).lower() == w or str(a.get("email", "")).lower() == w:
            return e
    return None


def _record_incoming(ctx, frm, ts):
    e = _find_contact(ctx, frm)
    if not e:
        e = KGEntity(id=ulid("ent"), tenant_id=ctx.actor.tenant_id, type="contact", name=frm, attrs={})
        ctx.db.add(e)
    e.attrs = {**(e.attrs or {}), "last_incoming_at": ts}
    ctx.db.flush()


def _within_window(ctx, to) -> bool:
    e = _find_contact(ctx, to)
    last = _parse_dt((e.attrs or {}).get("last_incoming_at")) if e else None
    return bool(last and (_now() - last) <= timedelta(hours=24))


def _enqueue(ctx, to, kind, payload):
    ctx.db.add(WhatsAppOutbox(id=ulid("wao"), tenant_id=ctx.actor.tenant_id, to=to,
                              kind=kind, payload=payload, status="queued",
                              attempts=0, next_retry_at=_now()))
    ctx.db.flush()


def _wa_send_needs_approval(ctx, kw):
    return not is_known_contact(ctx, kw.get("to", ""))   # U6 new-contact gate


@tool("whatsapp.send", "Send a free-form WhatsApp message (24-hour window enforced).",
      {"to": {"type": "string", "required": True}, "body": {"type": "string", "required": True}},
      permission="whatsapp.send", approval="conditional", writes_memory=True,
      needs_approval=_wa_send_needs_approval)
def whatsapp_send(ctx, to, body):
    # 24h customer-service window: free-form only allowed inside it (ARCHITECTURE §5)
    if not _within_window(ctx, to):
        return ToolResult(ok=False, error="validation",
                          summary="Outside the 24-hour window — use an approved template (whatsapp.send_template).")
    cl = get_provider_client(ctx, "whatsapp")
    payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": body}}
    status, data = _wa_post(cl.access_token, _wa_phone_id(), payload)
    if status == "rate_limited":
        _enqueue(ctx, to, "text", payload)
        return ToolResult(ok=True, data={"queued": True}, summary=f"Rate-limited — queued your WhatsApp to {to}; it'll retry.")
    return ToolResult(ok=True, data={"message_id": (data.get("messages") or [{}])[0].get("id")},
                      summary=f"Sent your WhatsApp to {to}.")


@tool("whatsapp.send_template", "Send a pre-approved WhatsApp template (allowed outside the 24h window).",
      {"to": {"type": "string", "required": True}, "template_id": {"type": "string", "required": True},
       "vars": {"type": "array"}}, permission="whatsapp.send", writes_memory=True)
def whatsapp_send_template(ctx, to, template_id, vars=None):
    cl = get_provider_client(ctx, "whatsapp")
    payload = {"messaging_product": "whatsapp", "to": to, "type": "template",
               "template": {"name": template_id, "language": {"code": "en"},
                            "components": [{"type": "body", "parameters": [{"type": "text", "text": str(v)} for v in (vars or [])]}]}}
    status, data = _wa_post(cl.access_token, _wa_phone_id(), payload)
    if status == "rate_limited":
        _enqueue(ctx, to, "template", payload)
        return ToolResult(ok=True, data={"queued": True}, summary=f"Rate-limited — queued the template to {to}.")
    return ToolResult(ok=True, data={"message_id": (data.get("messages") or [{}])[0].get("id")},
                      summary=f"Sent the “{template_id}” template to {to}.")


@tool("whatsapp.list_incoming", "List incoming WhatsApp messages (also refreshes the 24h window).",
      {"since": {"type": "string"}}, permission="whatsapp.read")
def whatsapp_list_incoming(ctx, since=None):
    cl = get_provider_client(ctx, "whatsapp")
    msgs = _wa_incoming(cl.access_token, since)
    for m in msgs:
        if m.get("from") and m.get("ts"):
            _record_incoming(ctx, m["from"], m["ts"])
    return ToolResult(ok=True, data={"messages": msgs}, summary=f"{len(msgs)} incoming WhatsApp message(s).")


@tool("whatsapp.quality_check", "Check the number's quality rating; alerts if degraded.",
      {}, permission="whatsapp.read")
def whatsapp_quality_check(ctx):
    cl = get_provider_client(ctx, "whatsapp")
    rating = _wa_quality(cl.access_token, _wa_phone_id())
    if rating != "GREEN":
        try:
            hub.emit(ctx.actor.tenant_id, "alert",
                     {"kind": "whatsapp_quality", "rating": rating,
                      "message": f"Your WhatsApp number quality is {rating} — ease off proactive sends."})
        except Exception:
            pass
        return ToolResult(ok=True, data={"rating": rating, "alert": True},
                          summary=f"⚠ WhatsApp number quality is {rating} — proactive sends throttled.")
    return ToolResult(ok=True, data={"rating": rating}, summary="WhatsApp number quality is GREEN.")


@tool("whatsapp.flush_queue", "Retry queued WhatsApp messages (backoff; dead-letter after 5 tries).",
      {}, permission="whatsapp.send")
def whatsapp_flush_queue(ctx):
    sent = dead = 0
    cl = get_provider_client(ctx, "whatsapp")
    rows = (ctx.db.query(WhatsAppOutbox)
            .filter_by(tenant_id=ctx.actor.tenant_id, status="queued")
            .filter(WhatsAppOutbox.next_retry_at <= _now()).all())
    for w in rows:
        try:
            status, _ = _wa_post(cl.access_token, _wa_phone_id(), w.payload)
        except Exception as e:
            status, w.last_error = "rate_limited", str(e)
        if status == "sent":
            w.status = "sent"; sent += 1
        else:
            w.attempts += 1
            if w.attempts >= 5:
                w.status = "dead"; dead += 1          # dead-letter
            else:
                w.next_retry_at = _now() + timedelta(seconds=2 ** w.attempts)   # exp backoff
    ctx.db.flush()
    return ToolResult(ok=True, data={"sent": sent, "dead": dead},
                      summary=f"WhatsApp queue: {sent} sent, {dead} dead-lettered.")


# ════════════════════════════ CONTACTS SYNC ═════════════════════════════════
def _people_list(token):
    """Google People connections (mockable)."""
    url = ("https://people.googleapis.com/v1/people/me/connections"
           "?personFields=names,emailAddresses,phoneNumbers&pageSize=200")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode() or "{}")
    except Exception as e:
        raise TransientError(str(e))
    out = []
    for c in data.get("connections", []):
        out.append({"name": (c.get("names") or [{}])[0].get("displayName"),
                    "email": (c.get("emailAddresses") or [{}])[0].get("value"),
                    "phone": (c.get("phoneNumbers") or [{}])[0].get("value")})
    return [c for c in out if c.get("name")]


@tool("contacts.sync", "Sync contacts from Google → resolve mentions like 'my dentist'.",
      {}, permission="contacts.write", writes_memory=True)
def contacts_sync(ctx):
    cl = get_provider_client(ctx, "gmail")
    n = 0
    for c in _people_list(cl.access_token):
        e = (ctx.db.query(KGEntity)
             .filter_by(tenant_id=ctx.actor.tenant_id, type="contact", name=c["name"]).first())
        attrs = {k: v for k, v in (("email", c.get("email")), ("phone", c.get("phone"))) if v}
        if e:
            e.attrs = {**(e.attrs or {}), **attrs}
        else:
            ctx.db.add(KGEntity(id=ulid("ent"), tenant_id=ctx.actor.tenant_id, type="contact",
                                name=c["name"], attrs=attrs))
        n += 1
    ctx.db.flush()
    return ToolResult(ok=True, data={"synced": n}, summary=f"Synced {n} contact(s) into your Second Brain.")


# ════════════════════════════ WEB (read-only, no auth) ══════════════════════
def _web_fetch_http(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 HERMUS"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", "ignore")
    except Exception as e:
        raise TransientError(str(e))


def _web_search(query, n):
    html = _web_fetch_http("https://lite.duckduckgo.com/lite/?" + urllib.parse.urlencode({"q": query}))
    out = []
    for m in re.finditer(r'<a[^>]+class="result-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        out.append({"url": m.group(1), "title": re.sub("<[^>]+>", "", m.group(2)).strip(), "snippet": ""})
        if len(out) >= n:
            break
    return out


@tool("web.search", "Search the web (read-only, no account). Results for Scribe to summarize.",
      {"query": {"type": "string", "required": True}, "n": {"type": "integer", "default": 5}},
      permission="web.read")
def web_search(ctx, query, n=5):
    results = _web_search(query, int(n))
    return ToolResult(ok=True, data={"results": results}, summary=f"Found {len(results)} web result(s) for “{query}”.")


@tool("web.fetch", "Read a web page (read-only). Returns clean text.",
      {"url": {"type": "string", "required": True}}, permission="web.read")
def web_fetch(ctx, url):
    html = _web_fetch_http(url)
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return ToolResult(ok=True, data={"text": text[:5000]}, summary=f"Read the page at {url}.")
