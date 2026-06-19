"""
Golden/integration tests for Prompt F (Calendar + Email + conditional approval).
Mocked provider — no network. Covers the new-contact gate, the destructive
(has-attendees) gate, the citation block on send, and bill detection.

Run:  python -m pytest tests/test_tier2_calendar_email.py -q
Or:   python tests/test_tier2_calendar_email.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import connections as C  # noqa: E402
from app import tier2_tools as T2  # noqa: E402
from app.security import ulid  # noqa: E402
from app.tools import Actor, ToolContext, call_tool  # noqa: E402


def _mkdb():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def _ctx(db, approved=False):
    return ToolContext(actor=Actor("tnt_f", "usr_f", "Aria", {"*"}), db=db, approved=approved)


def _connect(db, provider):
    from app.models import Connection
    key = C.vault_put(db, "tnt_f", {"access_token": "tok", "refresh_token": "r",
                                    "expires_at": int(time.time()) + 9999})
    db.add(Connection(id=ulid("con"), tenant_id="tnt_f", user_id="usr_f", provider=provider,
                      status="connected", vault_secret_key=key))
    db.flush()


def _contact(db, name, email=None):
    from app.models import KGEntity
    db.add(KGEntity(id=ulid("ent"), tenant_id="tnt_f", type="contact", name=name,
                    attrs={"email": email} if email else {}))
    db.flush()


def _mock_api(method, url, token, params=None, body=None):
    path = url.split("?")[0]
    # calendar
    if path.endswith("/calendars/primary/events") and method == "POST":
        return {"id": "ev1", "htmlLink": "http://cal/ev1"}
    if path.endswith("/events/withppl") and method == "GET":
        return {"id": "withppl", "attendees": [{"email": "x@y.com"}]}
    if path.endswith("/events/solo") and method == "GET":
        return {"id": "solo"}
    if "/events/" in path and method == "DELETE":
        return {}
    if path.endswith("/events") and method == "GET":
        return {"items": []}
    # gmail
    if path.endswith("/messages/send"):
        return {"id": "sent1"}
    if path.endswith("/messages/m1") and method == "GET":
        return {"id": "m1", "snippet": "Your electricity bill is due 2026-07-01, amount 1500"}
    if path.endswith("/messages") and method == "GET":
        return {"messages": [{"id": "m1"}]}
    return {}


def _patch():
    orig = T2._api
    T2._api = _mock_api
    return lambda: setattr(T2, "_api", orig)


# ── conditional approval: new-contact gate ───────────────────────────────────
def test_create_event_known_contact_runs():
    r0 = _patch()
    try:
        db = _mkdb(); _connect(db, "google_calendar"); _contact(db, "Ravi", "ravi@x.com")
        r = call_tool("calendar.create_event", _ctx(db), title="Sync",
                      start="2026-07-01T10:00:00Z", end="2026-07-01T10:30:00Z", attendees=["ravi@x.com"])
        assert r.ok and r.data["event_id"] == "ev1"
    finally:
        r0()


def test_create_event_new_contact_gated_then_runs():
    r0 = _patch()
    try:
        db = _mkdb(); _connect(db, "google_calendar")
        g = call_tool("calendar.create_event", _ctx(db), title="Sync",
                      start="2026-07-01T10:00:00Z", end="2026-07-01T10:30:00Z", attendees=["stranger@x.com"])
        assert g.ok is False and g.error == "user_input_needed", "inviting a new contact must gate (U6)"
        a = call_tool("calendar.create_event", _ctx(db, approved=True), title="Sync",
                      start="2026-07-01T10:00:00Z", end="2026-07-01T10:30:00Z", attendees=["stranger@x.com"])
        assert a.ok and a.data["event_id"] == "ev1"
    finally:
        r0()


# ── conditional approval: destructive (has-attendees) gate ───────────────────
def test_cancel_event_gate_depends_on_attendees():
    r0 = _patch()
    try:
        db = _mkdb(); _connect(db, "google_calendar")
        gated = call_tool("calendar.cancel_event", _ctx(db), id="withppl")
        assert gated.ok is False and gated.error == "user_input_needed", "event with attendees gates"
        solo = call_tool("calendar.cancel_event", _ctx(db), id="solo")
        assert solo.ok is True, "solo event cancels without approval"
    finally:
        r0()


# ── email gating + citation block ────────────────────────────────────────────
def test_email_send_new_recipient_gated():
    r0 = _patch()
    try:
        db = _mkdb(); _connect(db, "gmail")
        d = call_tool("email.draft", _ctx(db), to="stranger@x.com", subject="Hi", body="hello there")
        send = call_tool("email.send", _ctx(db), draft_id=d.data["draft_id"])
        assert send.ok is False and send.error == "user_input_needed", "new recipient gates send (U6)"
    finally:
        r0()


def test_email_send_known_no_money_sends():
    r0 = _patch()
    try:
        db = _mkdb(); _connect(db, "gmail"); _contact(db, "Ravi", "ravi@x.com")
        d = call_tool("email.draft", _ctx(db), to="ravi@x.com", subject="Hi", body="see you tomorrow")
        send = call_tool("email.send", _ctx(db), draft_id=d.data["draft_id"])
        assert send.ok is True and send.data["message_id"] == "sent1"
    finally:
        r0()


def test_email_send_citation_block():
    """Even when approved, a figure not in the source must block the send (§5)."""
    r0 = _patch()
    try:
        db = _mkdb(); _connect(db, "gmail"); _contact(db, "Ravi", "ravi@x.com")
        d = call_tool("email.draft", _ctx(db), to="ravi@x.com", subject="Invoice",
                      body="The amount is 9999.", source="invoice total amount 1500")
        send = call_tool("email.send", _ctx(db, approved=True), draft_id=d.data["draft_id"])
        assert send.ok is False and send.error == "validation" and "Blocked" in send.summary
    finally:
        r0()


# ── detect_bills → deadline.track ────────────────────────────────────────────
def test_detect_bills_creates_deadlines():
    from app.models import Reminder
    r0 = _patch()
    try:
        db = _mkdb(); _connect(db, "gmail")
        r = call_tool("email.detect_bills", _ctx(db)); db.commit()
        assert r.ok and r.data["bills"]
        assert db.query(Reminder).filter_by(kind="deadline").count() == 1
    finally:
        r0()


def test_calendar_list_and_find_slots():
    r0 = _patch()
    try:
        db = _mkdb(); _connect(db, "google_calendar")
        lst = call_tool("calendar.list_events", _ctx(db),
                        time_min="2026-07-01T00:00:00Z", time_max="2026-07-02T00:00:00Z")
        assert lst.ok
        slots = call_tool("calendar.find_slots", _ctx(db), duration_min=30,
                          time_min="2026-07-01T09:00:00+00:00", time_max="2026-07-01T17:00:00+00:00")
        assert slots.ok and slots.data["slots"], "an empty calendar yields a free slot"
    finally:
        r0()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn(); print(f"  PASS  {fn.__name__}"); passed += 1
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}: {e}")
        except Exception as e:
            import traceback; traceback.print_exc(); print(f"  ERROR {fn.__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
