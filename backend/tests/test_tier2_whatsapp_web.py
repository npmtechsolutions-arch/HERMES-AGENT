"""
Golden tests for Prompt G (WhatsApp + contacts.sync + web). Mocked provider — no
network. Covers the 24-hour window rule (free-form vs template), the new-contact
gate, queue/retry on rate-limit + dead-letter, quality alert, contacts sync, web.

Run:  python -m pytest tests/test_tier2_whatsapp_web.py -q
Or:   python tests/test_tier2_whatsapp_web.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import connections as C  # noqa: E402
from app import tier2_tools as T2  # noqa: E402
from app.models import now as _now  # noqa: E402
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
    return ToolContext(actor=Actor("tnt_g", "usr_g", "Aria", {"*"}), db=db, approved=approved)


def _connect(db, provider):
    from app.models import Connection
    key = C.vault_put(db, "tnt_g", {"access_token": "tok", "expires_at": 0})  # no expiry
    db.add(Connection(id=ulid("con"), tenant_id="tnt_g", user_id="usr_g", provider=provider,
                      status="connected", vault_secret_key=key))
    db.flush()


def _contact(db, name, email=None, last_incoming=None):
    from app.models import KGEntity
    attrs = {}
    if email:
        attrs["email"] = email
    if last_incoming:
        attrs["last_incoming_at"] = last_incoming
    db.add(KGEntity(id=ulid("ent"), tenant_id="tnt_g", type="contact", name=name, attrs=attrs))
    db.flush()


def _patch(name, fn):
    orig = getattr(T2, name)
    setattr(T2, name, fn)
    return lambda: setattr(T2, name, orig)


# ── 24-hour window rule ──────────────────────────────────────────────────────
def test_whatsapp_send_outside_window_blocked():
    db = _mkdb(); _connect(db, "whatsapp"); _contact(db, "Ravi")   # known, but no recent inbound
    r = call_tool("whatsapp.send", _ctx(db), to="Ravi", body="hi")
    assert r.ok is False and "template" in r.summary.lower(), "free-form blocked outside the 24h window"


def test_whatsapp_send_inside_window_sends():
    restore = _patch("_wa_post", lambda *a, **k: ("sent", {"messages": [{"id": "wamid1"}]}))
    try:
        db = _mkdb(); _connect(db, "whatsapp")
        _contact(db, "Ravi", last_incoming=_now().isoformat())   # messaged us → window open
        r = call_tool("whatsapp.send", _ctx(db), to="Ravi", body="thanks!")
        assert r.ok and r.data["message_id"] == "wamid1"
    finally:
        restore()


def test_whatsapp_new_contact_gated():
    db = _mkdb(); _connect(db, "whatsapp")
    r = call_tool("whatsapp.send", _ctx(db), to="Stranger", body="hi")
    assert r.ok is False and r.error == "user_input_needed", "new contact gates (U6)"


def test_send_template_allowed_outside_window():
    restore = _patch("_wa_post", lambda *a, **k: ("sent", {"messages": [{"id": "tmpl1"}]}))
    try:
        db = _mkdb(); _connect(db, "whatsapp"); _contact(db, "Ravi")   # no window needed for templates
        r = call_tool("whatsapp.send_template", _ctx(db), to="Ravi", template_id="reminder", vars=["10am"])
        assert r.ok and r.data["message_id"] == "tmpl1"
    finally:
        restore()


# ── queue / retry / dead-letter on rate limit ────────────────────────────────
def test_queue_and_retry_on_rate_limit():
    from app.models import WhatsAppOutbox
    db = _mkdb(); _connect(db, "whatsapp"); _contact(db, "Ravi", last_incoming=_now().isoformat())
    r0 = _patch("_wa_post", lambda *a, **k: ("rate_limited", None))
    try:
        r = call_tool("whatsapp.send", _ctx(db), to="Ravi", body="busy line"); db.commit()
        assert r.ok and r.data.get("queued") is True
        assert db.query(WhatsAppOutbox).filter_by(status="queued").count() == 1
    finally:
        r0()
    r1 = _patch("_wa_post", lambda *a, **k: ("sent", {"messages": [{"id": "z"}]}))
    try:
        f = call_tool("whatsapp.flush_queue", _ctx(db)); db.commit()
        assert f.data["sent"] == 1
        assert db.query(WhatsAppOutbox).filter_by(status="sent").count() == 1
    finally:
        r1()


def test_dead_letter_after_max_attempts():
    from app.models import WhatsAppOutbox
    db = _mkdb(); _connect(db, "whatsapp")
    w = WhatsAppOutbox(id=ulid("wao"), tenant_id="tnt_g", to="X", kind="text", payload={},
                       status="queued", attempts=4, next_retry_at=_now())
    db.add(w); db.commit()
    restore = _patch("_wa_post", lambda *a, **k: ("rate_limited", None))
    try:
        f = call_tool("whatsapp.flush_queue", _ctx(db)); db.commit()
        assert f.data["dead"] == 1
        assert db.query(WhatsAppOutbox).filter_by(status="dead").count() == 1, "dead-lettered after 5 tries"
    finally:
        restore()


# ── quality monitoring ───────────────────────────────────────────────────────
def test_quality_check_alerts_when_degraded():
    db = _mkdb(); _connect(db, "whatsapp")
    red = _patch("_wa_quality", lambda *a, **k: "RED")
    try:
        r = call_tool("whatsapp.quality_check", _ctx(db))
        assert r.ok and r.data["alert"] is True and "RED" in r.summary
    finally:
        red()
    green = _patch("_wa_quality", lambda *a, **k: "GREEN")
    try:
        assert call_tool("whatsapp.quality_check", _ctx(db)).data.get("alert") in (None, False)
    finally:
        green()


# ── contacts sync ─────────────────────────────────────────────────────────────
def test_contacts_sync_upserts_kg():
    from app.models import KGEntity
    db = _mkdb(); _connect(db, "gmail")
    restore = _patch("_people_list", lambda token: [{"name": "Dr Mehta", "email": "m@x.com", "phone": "123"}])
    try:
        r = call_tool("contacts.sync", _ctx(db)); db.commit()
        assert r.ok and r.data["synced"] == 1
        e = db.query(KGEntity).filter_by(type="contact", name="Dr Mehta").first()
        assert e and e.attrs.get("email") == "m@x.com"
    finally:
        restore()


# ── web (read-only, no auth) ─────────────────────────────────────────────────
def test_web_search_and_fetch():
    db = _mkdb()
    s = _patch("_web_search", lambda q, n: [{"title": "Result", "url": "http://x", "snippet": ""}])
    f = _patch("_web_fetch_http", lambda url: "<html><body>Hello <script>bad()</script>World</body></html>")
    try:
        res = call_tool("web.search", _ctx(db), query="best dentist nearby")
        assert res.ok and len(res.data["results"]) == 1
        page = call_tool("web.fetch", _ctx(db), url="http://x")
        assert page.ok and "Hello World" in page.data["text"] and "bad()" not in page.data["text"]
    finally:
        s(); f()


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
