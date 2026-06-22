"""
Tests for the direct feature-run endpoint (Doc 29 §5.1 live mode, Option B). A
card runs EXACTLY its tool, and a gated tool returns needs_approval instead of
executing — the safety gate, visible to the UI.

Run:  python -m pytest tests/test_feature_run.py -q
Or:   python tests/test_feature_run.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException

from app.routers import feature_run as FR


class _P:
    kind = "user"; user_id = "usr_r"; tenant_id = "tnt_r"; roles = []; email = "r@x.com"


def _mkdb():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def test_run_creates_real_reminder_exactly():
    from app.models import Reminder
    db = _mkdb()
    out = FR.run_feature("reminder.create",
                         FR.RunIn(params={"text": "pay rent", "due_at": "2026-07-01T09:00:00+00:00"}),
                         _P(), db)
    assert out["ok"] and out["tool"] == "reminder.create" and out["agent"] == "Scheduler"
    r = db.query(Reminder).filter_by(tenant_id="tnt_r").one()
    assert r.text == "pay rent"


def test_gated_tool_returns_needs_approval_and_does_not_run():
    from app.models import MemoryItem
    from app.security import ulid
    db = _mkdb()
    m = MemoryItem(id=ulid("mem"), tenant_id="tnt_r", memory_class="personal",
                   title="secret", source_type="note", body="x", tier="hot")
    db.add(m); db.commit()
    # "Forget this" (memory.forget, approval=required) must NOT delete on a plain click
    out = FR.run_feature("memory.forget", FR.RunIn(params={"id": m.id}), _P(), db)
    assert out["needs_approval"] is True and not out["ok"]
    assert db.get(MemoryItem, m.id).tier == "hot", "must not delete without approval"
    # approved → runs
    out2 = FR.run_feature("memory.forget", FR.RunIn(params={"id": m.id}, approved=True), _P(), db)
    assert out2["ok"] and db.get(MemoryItem, m.id).tier == "deleted"


def test_unknown_feature_404():
    db = _mkdb()
    try:
        FR.run_feature("no.such.tool", FR.RunIn(), _P(), db)
        assert False
    except HTTPException as e:
        assert e.status_code == 404


def test_live_note_runs_exact_tool():
    from app.models import MemoryItem
    db = _mkdb()
    out = FR.run_feature("note.create", FR.RunIn(params={"text": "buy milk"}), _P(), db)
    assert out["ok"] and out["tool"] == "note.create"
    assert db.query(MemoryItem).filter_by(tenant_id="tnt_r", source_type="note").count() >= 1


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
