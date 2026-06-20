"""
Golden tests for Prompt H (Tier-3: prepare-and-handoff + browser automation).
Self-contained (in-memory SQLite); the browser runner is mocked. Covers handoff
card generation + confirm routing (incl. money-never-autonomous), and the browser
recipe happy-path + captcha-handoff + opt-in/approval guards.

Run:  python -m pytest tests/test_tier3_handoff_browser.py -q
Or:   python tests/test_tier3_handoff_browser.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import tier3_tools as T3  # noqa: E402
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
    return ToolContext(actor=Actor("tnt_h", "usr_h", "Aria", {"*"}), db=db, approved=approved)


def _patch(name, fn):
    orig = getattr(T3, name)
    setattr(T3, name, fn)
    return lambda: setattr(T3, name, orig)


# ── handoff: card generation + confirm routing ───────────────────────────────
def test_handoff_prepare_makes_card_and_record():
    from app.models import Handoff
    db = _mkdb()
    r = call_tool("handoff.prepare", _ctx(db), action_type="restaurant_booking",
                  payload={"venue": "Spice Garden", "date": "Fri", "time": "8pm", "party_size": 4,
                           "link": "http://book/spice"})
    db.commit()
    assert r.ok and r.data["method"] == "link"
    assert "Spice Garden" in r.data["card"]["title"] and "Confirm" in r.data["card"]["confirm_label"]
    assert db.query(Handoff).filter_by(status="prepared").count() == 1


def test_handoff_confirm_link_routing():
    db = _mkdb()
    p = call_tool("handoff.prepare", _ctx(db), action_type="restaurant_booking",
                  payload={"venue": "X", "link": "http://book/x"})
    c = call_tool("handoff.confirm", _ctx(db), handoff_id=p.data["handoff_id"]); db.commit()
    assert c.ok and c.data["route"]["action"] == "open_link" and c.data["route"]["url"] == "http://book/x"


def test_handoff_confirm_message_routes_to_gated_send():
    db = _mkdb()
    p = call_tool("handoff.prepare", _ctx(db), action_type="message",
                  payload={"to": "Ravi", "draft_message": "Table confirmed?"})
    c = call_tool("handoff.confirm", _ctx(db), handoff_id=p.data["handoff_id"])
    assert c.ok and c.data["route"]["action"] == "whatsapp_send" and c.data["route"]["to"] == "Ravi"


def test_bill_payment_never_autonomous():
    """Money is never moved by us — bill_payment only ever opens the page for the user."""
    db = _mkdb()
    p = call_tool("handoff.prepare", _ctx(db), action_type="bill_payment",
                  payload={"biller": "Electricity", "amount": "₹1500", "link": "http://pay/elec"})
    assert "never move money" in p.summary.lower()
    c = call_tool("handoff.confirm", _ctx(db), handoff_id=p.data["handoff_id"])
    assert c.data["route"]["action"] == "open_link", "confirm only opens the payment page; user pays"


def test_handoff_confirm_twice_blocked():
    db = _mkdb()
    p = call_tool("handoff.prepare", _ctx(db), action_type="cab", payload={"link": "http://ride"})
    call_tool("handoff.confirm", _ctx(db), handoff_id=p.data["handoff_id"]); db.commit()
    again = call_tool("handoff.confirm", _ctx(db), handoff_id=p.data["handoff_id"])
    assert again.ok is False, "a confirmed handoff can't be confirmed again"


# ── browser automation ───────────────────────────────────────────────────────
def _recipe(db, enabled=True):
    from app.models import BrowserRecipe
    rid = ulid("brc")
    db.add(BrowserRecipe(id=rid, tenant_id="tnt_h", user_id="usr_h", name="reorder",
                         steps=[{"goto": "x"}], enabled=enabled))
    db.flush()
    return rid


def test_browser_requires_approval():
    db = _mkdb(); rid = _recipe(db)
    r = call_tool("browser.perform", _ctx(db), recipe_id=rid)   # not approved
    assert r.ok is False and r.error == "user_input_needed", "browser.perform is approval=required"


def test_browser_disabled_recipe_blocked():
    db = _mkdb(); rid = _recipe(db, enabled=False)
    r = call_tool("browser.perform", _ctx(db, approved=True), recipe_id=rid)
    assert r.ok is False and "off" in r.summary.lower(), "opt-in: disabled recipe won't run"


def test_browser_happy_path():
    restore = _patch("_run_recipe", lambda steps, data: {"ok": True, "data": {"order": "placed"}, "summary": "Reordered."})
    try:
        db = _mkdb(); rid = _recipe(db, enabled=True)
        r = call_tool("browser.perform", _ctx(db, approved=True), recipe_id=rid, data={"qty": 2})
        assert r.ok and r.data["order"] == "placed"
    finally:
        restore()


def test_browser_captcha_hands_back_to_user():
    restore = _patch("_run_recipe", lambda steps, data: {"needs_human": True, "screenshot": "shot.png", "url": "http://site"})
    try:
        db = _mkdb(); rid = _recipe(db, enabled=True)
        r = call_tool("browser.perform", _ctx(db, approved=True), recipe_id=rid)
        assert r.ok is False and r.error == "user_input_needed"
        assert r.data["screenshot"] == "shot.png" and r.data["url"] == "http://site"
    finally:
        restore()


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
