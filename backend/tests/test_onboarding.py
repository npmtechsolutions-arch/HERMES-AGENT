"""
Tests for the first-run Guided Setup wizard (Doc 26 Prompt I). Verifies resume,
that "About you" seeds preferences + SOUL, that the first-task step invokes the
REAL assistant (a reminder is actually created — not a fake demo), and reset.

Run:  python -m pytest tests/test_onboarding.py -q
Or:   python tests/test_onboarding.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.routers import onboarding as O  # noqa: E402


class _P:
    kind = "user"; user_id = "usr_o"; tenant_id = "tnt_o"; roles = []; email = "o@x.com"


def _mkdb():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def test_state_created_and_resumes():
    db = _mkdb(); p = _P()
    s1 = O.get_state(p, db)
    assert s1["step"] == 1 and s1["total"] == 6 and not s1["completed"]
    O.nav(O.Nav(step=3), p, db)               # advance
    s2 = O.get_state(p, db)                    # fresh read → resumes at 3
    assert s2["step"] == 3


def test_first_task_step_is_required_and_others_skippable():
    db = _mkdb(); p = _P()
    O.nav(O.Nav(step=2, skip_key="about"), p, db)
    O.nav(O.Nav(step=4, skip_key="first_task"), p, db)   # required → ignored
    s = O.get_state(p, db)
    assert "about" in s["skipped"] and "first_task" not in s["skipped"]


def test_about_seeds_preferences_and_soul():
    from app.models import MemoryItem
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["HERMUS_DATA_ROOT"] = tmp
        try:
            db = _mkdb(); p = _P()
            r = O.about(O.About(name="Asha", language="Hindi", role="freelance designer"), p, db)
            assert r["ok"] and r["saved"]["name"] == "Asha"
            prefs = db.query(MemoryItem).filter_by(tenant_id="tnt_o", source_type="preference").all()
            assert {pp.body for pp in prefs} >= {"My name is Asha."}
            assert O.get_state(p, db)["step"] >= 3          # advanced past About
            from app import projections as P
            assert "Asha" in P.load_soul()                  # SOUL projection seeded
        finally:
            os.environ.pop("HERMUS_DATA_ROOT", None)


def test_first_task_invokes_real_planner_and_creates_reminder():
    from app.models import Reminder
    db = _mkdb(); p = _P()
    out = O.first_task(O.FirstTask(text=None), p, db)        # default example
    assert out["ok"] and out["result"]["tool"] == "reminder.create"
    assert db.query(Reminder).filter_by(tenant_id="tnt_o").count() == 1, "a REAL reminder, not a demo"
    assert O.get_state(p, db)["step"] >= 5


def test_complete_then_reset():
    db = _mkdb(); p = _P()
    c = O.complete(p, db)
    assert c["ok"] and O.get_state(p, db)["completed"] is True
    r = O.reset(p, db)
    assert r["completed"] is False and r["step"] == 1


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
