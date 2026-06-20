"""
Tests for the assistant spine — the integration step that makes the user guide
real. Each test feeds a sentence STRAIGHT FROM THE GUIDE and asserts the right
tool ran and produced the right effect. Self-contained (in-memory SQLite).

Run:  python -m pytest tests/test_assistant.py -q
Or:   python tests/test_assistant.py
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import assistant as A  # noqa: E402
from app.assistant import parse_when, route_intent, run_assistant  # noqa: E402

NOW = datetime(2026, 6, 18, 9, 0, tzinfo=timezone.utc)   # a Thursday


def _mkdb():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def _run(db, text, approved=False):
    return run_assistant(db, tenant_id="tnt_a", user_id="usr_a", text=text, approved=approved)


# ── routing (pure, no db) ─────────────────────────────────────────────────────
def test_routes_cover_guide_examples():
    cases = {
        "Remind me to call the bank tomorrow at 11am.": "reminder.create",
        "Remind me to take my medicine every morning at 8.": "reminder.create",
        "Plan my day.": "briefing.compose",
        "What's on my plate today?": "briefing.compose",
        "Remember my landlord's name is Mr. Sharma.": "memory.write",
        "Track my electricity bill every month.": "finance.track_subscription",
        "What subscriptions am I paying for?": "finance.budget_status",
        "Write a thank-you note to my client.": "document.generate",
        "Make me an invoice for ₹15,000 for consulting.": "document.generate",
        "Research the best laptops under ₹60,000 and summarize.": "web.search",
        "Book a table for 4 at Spice Garden Friday 8pm.": "handoff.prepare",
        "Read my urgent emails.": "email.list",
        "Am I free Thursday morning?": "calendar.find_slots",
        "What can you do?": "__help__",
    }
    for text, expected in cases.items():
        routed = route_intent(text, NOW)
        got = routed[0] if routed else "(none→memory.search)"
        assert got == expected, f"{text!r} → {got}, expected {expected}"


def test_recall_question_falls_back_to_memory_search():
    assert route_intent("What's my landlord's name?", NOW) is None   # → memory.search


def test_parse_when_tomorrow_11am():
    iso, repeat = parse_when("call the bank tomorrow at 11am", NOW)
    dt = datetime.fromisoformat(iso)
    assert dt.day == 19 and dt.hour == 11 and repeat == "none"


def test_parse_when_every_morning_is_daily_at_8():
    iso, repeat = parse_when("take my medicine every morning at 8", NOW)
    assert repeat == "daily" and datetime.fromisoformat(iso).hour == 8


def test_parse_when_weekday_friday():
    iso, _ = parse_when("dentist appointment on friday", NOW)
    assert datetime.fromisoformat(iso).weekday() == 4   # Friday


# ── end-to-end (real call_tool, real db effects) ──────────────────────────────
def test_reminder_command_creates_a_real_reminder():
    from app.models import Reminder
    db = _mkdb()
    out = _run(db, "Remind me to call the bank tomorrow at 11am."); db.commit()
    assert out["ok"] and out["tool"] == "reminder.create"
    r = db.query(Reminder).filter_by(tenant_id="tnt_a").one()
    assert "bank" in r.text and r.due_at.hour == 11 and r.status == "active"


def test_remember_then_recall_roundtrip():
    db = _mkdb()
    w = _run(db, "Remember my landlord's name is Mr. Sharma."); db.commit()
    assert w["ok"] and w["tool"] == "memory.write"
    r = _run(db, "What's my landlord's name?")        # recall → memory.search
    assert r["tool"] == "memory.search"
    blob = (r["summary"] + str(r["data"])).lower()
    assert "sharma" in blob


def test_track_subscription_command():
    from app.models import KGEntity
    db = _mkdb()
    out = _run(db, "Track my Netflix subscription, ₹649 every month."); db.commit()
    assert out["ok"] and out["tool"] == "finance.track_subscription"
    assert db.query(KGEntity).filter_by(type="Subscription").count() == 1


def test_invoice_generates_a_local_document():
    db = _mkdb()
    out = _run(db, "Make me an invoice for ₹15,000 for consulting."); db.commit()
    assert out["ok"] and out["tool"] == "document.generate"
    assert out["artifacts"] and out["artifacts"][0]["title"] == "Invoice"


def test_booking_prepares_a_one_tap_handoff_not_autonomous():
    from app.models import Handoff
    db = _mkdb()
    out = _run(db, "Book a table for 4 at Spice Garden Friday 8pm."); db.commit()
    assert out["ok"] and out["tool"] == "handoff.prepare"
    assert db.query(Handoff).count() == 1, "prepared, awaiting the user's one-tap confirm"


def test_help_lists_capabilities():
    db = _mkdb()
    out = _run(db, "What can you do?")
    assert out["ok"] and "Remind me" in out["summary"]


def test_undo_cancels_last_reminder():
    from app.models import Reminder
    db = _mkdb()
    _run(db, "Remind me to call the bank tomorrow at 11am."); db.commit()
    out = _run(db, "Stop that"); db.commit()
    assert out["ok"]
    assert db.query(Reminder).filter_by(status="active").count() == 0


def test_capabilities_and_registry_populated():
    caps = A.capabilities()
    keys = {g["key"] for g in caps["groups"]}
    assert caps["count"] >= 40 and {"reminders", "money"} <= keys


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
