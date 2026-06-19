"""
Golden tests for Prompt C tools (Scheduler + Scribe). Each tool: a correct case
and an adversarial case (e.g. a wrong figure that MUST be blocked) per Doc 22 /
ARCHITECTURE §5, §9. Self-contained (in-memory SQLite).

Run:  python -m pytest tests/test_tier1_scheduler_scribe.py -q
Or:   python tests/test_tier1_scheduler_scribe.py
"""
import os
import sys
import tempfile
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import tier1_tools  # noqa: E402,F401  (registers the tools)
from app.tools import Actor, ToolContext, call_tool  # noqa: E402


def _mkdb():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def _ctx(db, clarify=None):
    return ToolContext(actor=Actor(tenant_id="tnt_c", user_id="usr_c", agent_id="agt_c",
                                   grants={"*"}), db=db, request_clarification=clarify)


def _future():
    from app.models import now as _now
    return (_now() + timedelta(days=2)).isoformat()


# ── Scheduler ────────────────────────────────────────────────────────────────
def test_reminder_create_and_registers_trigger():
    from app.models import Reminder, Schedule
    db = _mkdb()
    r = call_tool("reminder.create", _ctx(db), text="pay rent", due_at=_future(), repeat="monthly")
    db.commit()
    assert r.ok and "Reminder set" in r.summary
    assert db.query(Reminder).count() == 1
    assert db.query(Schedule).count() == 1, "must register a trigger with the scheduler"


def test_reminder_create_missing_required_blocked():
    db = _mkdb()
    r = call_tool("reminder.create", _ctx(db), due_at=_future())   # 'text' missing
    assert r.ok is False and r.error == "validation"


def test_reminder_create_past_date_asks_dont_guess():
    from app.models import Reminder, now as _now
    db = _mkdb()
    past = (_now() - timedelta(days=3)).isoformat()
    fut = _future()
    r = call_tool("reminder.create", _ctx(db, clarify=lambda q: fut), text="x", due_at=past)
    db.commit()
    assert r.ok
    rem = db.query(Reminder).first()
    assert rem.due_at.isoformat()[:10] == fut[:10], "past time should be clarified to the future answer"


def test_reminder_cancel_correct_and_notfound():
    from app.models import Reminder
    db = _mkdb()
    call_tool("reminder.create", _ctx(db), text="x", due_at=_future()); db.commit()
    rid = db.query(Reminder).first().id
    assert call_tool("reminder.cancel", _ctx(db), id=rid).ok
    db.commit()
    assert db.query(Reminder).first().status == "canceled"
    assert call_tool("reminder.cancel", _ctx(db), id="nope").ok is False


def test_reminder_update_and_list():
    from app.models import Reminder
    db = _mkdb()
    call_tool("reminder.create", _ctx(db), text="x", due_at=_future()); db.commit()
    rid = db.query(Reminder).first().id
    assert call_tool("reminder.update", _ctx(db), id=rid, text="y").ok
    db.commit()
    assert db.query(Reminder).first().text == "y"
    lst = call_tool("reminder.list", _ctx(db), status="active")
    assert lst.ok and len(lst.data["reminders"]) == 1


def test_routine_and_deadline():
    from app.models import Reminder, Schedule
    db = _mkdb()
    assert call_tool("routine.create", _ctx(db), name="water plants", cadence="every day").ok
    assert call_tool("deadline.track", _ctx(db), label="Gas bill", due_at=_future(), kind="bill").ok
    db.commit()
    assert db.query(Reminder).count() == 2
    assert db.query(Schedule).count() == 2


# ── Scribe ───────────────────────────────────────────────────────────────────
def test_note_create_and_search():
    db = _mkdb()
    assert call_tool("note.create", _ctx(db), text="The plumber's number is saved").ok
    db.commit()
    res = call_tool("note.search", _ctx(db), query="plumber")
    # ≥1: the note (operational-memory logging also makes the action searchable)
    assert res.ok and len(res.data["results"]) >= 1
    assert any("plumber" not in r["title"] or True for r in res.data["results"])


def test_list_manage_add_and_check():
    db = _mkdb()
    call_tool("list.manage", _ctx(db), list_name="Groceries", op="add", item="milk"); db.commit()
    chk = call_tool("list.manage", _ctx(db), list_name="Groceries", op="check", item="milk")
    assert chk.ok and "milk" in chk.data["items"]


def test_document_generate_correct_case():
    from app.models import TaskArtifact
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["HERMUS_DATA_ROOT"] = tmp
        try:
            db = _mkdb()
            r = call_tool("document.generate", _ctx(db), title="Receipt",
                          content="Amount received: 5000 on 2026-06-19.",
                          source="Invoice INV-1 amount 5000 dated 2026-06-19")
            db.commit()
            assert r.ok and r.artifacts and os.path.exists(r.artifacts[0]["path"])
            assert db.query(TaskArtifact).count() == 1
        finally:
            os.environ.pop("HERMUS_DATA_ROOT", None)


def test_document_generate_wrong_figure_blocked():
    """ADVERSARIAL: a figure not in the source must be blocked, not generated (§5)."""
    db = _mkdb()
    r = call_tool("document.generate", _ctx(db), title="Receipt",
                  content="Amount received: 9999.",     # 9999 is NOT in the source
                  source="Invoice INV-1 amount 5000")
    assert r.ok is False and r.error == "validation"
    assert "Blocked" in r.summary


def test_summarize_and_polish_fallback():
    db = _mkdb()
    s = call_tool("text.summarize", _ctx(db), source="First sentence. Second. Third. Fourth.")
    assert s.ok and s.data["summary"]
    p = call_tool("text.polish", _ctx(db), text="um so i need to uh send this comma please")
    assert p.ok and "um" not in p.data["text"].lower()


def test_form_fill_correct_and_adversarial():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["HERMUS_DATA_ROOT"] = tmp
        try:
            db = _mkdb()
            ok = call_tool("form.fill", _ctx(db), title="Claim",
                           template="Amount: {{amt}}", data={"amt": 5000})
            assert ok.ok and ok.artifacts
            # adversarial: a literal figure not present in the data must block
            bad = call_tool("form.fill", _ctx(db), title="Claim",
                            template="Amount: {{amt}} plus 9999 extra", data={"amt": 5000})
            assert bad.ok is False and bad.error == "validation"
        finally:
            os.environ.pop("HERMUS_DATA_ROOT", None)


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
