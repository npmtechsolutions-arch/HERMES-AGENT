"""
Tests for the feature-schedule endpoints (Doc 29 §5.1b — endpoints only). Verifies
create/list/edit/pause/resume/skip-next/runs + cadence→next-run, validation, the
workflow/feature separation, and that creating a schedule does NOT execute the
tool (the executor is the next phase).

Run:  python -m pytest tests/test_feature_schedules.py -q
Or:   python tests/test_feature_schedules.py
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException

from app.routers import feature_schedules as FS


class _P:
    kind = "user"; user_id = "usr_s"; tenant_id = "tnt_s"; roles = []; email = "s@x.com"


def _mkdb():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def _create(db, **kw):
    body = FS.ScheduleIn(feature_key=kw.get("feature_key", "reminder.create"),
                         params=kw.get("params", {"text": "pay rent", "due_at": "2026-07-01T09:00:00"}),
                         cadence=kw.get("cadence", {"type": "monthly", "day": 1, "time": "09:00"}),
                         instructions=kw.get("instructions"), label=kw.get("label"))
    return FS.create(body, _P(), db)


# ── next_run cadence math (pure) ──────────────────────────────────────────────
def test_next_run_cadences():
    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)   # a Thursday, noon
    d = FS.next_run({"type": "daily", "time": "09:00"}, now)
    assert d.hour == 9 and d.day == 19                         # 9am already passed → tomorrow
    w = FS.next_run({"type": "weekly", "weekday": 0, "time": "08:00"}, now)
    assert w.weekday() == 0 and w > now                        # next Monday
    m = FS.next_run({"type": "monthly", "day": 1, "time": "09:00"}, now)
    assert m.day == 1 and m.month == 7                         # 1st already passed → next month
    assert FS.next_run({"type": "custom", "cron": "0 9 * * 1"}, now) > now


# ── create ────────────────────────────────────────────────────────────────────
def test_create_feature_schedule():
    from app.models import Reminder, Schedule
    db = _mkdb()
    out = _create(db); db.commit()
    assert out["feature_key"] == "reminder.create" and out["agent"] == "Scheduler"
    assert out["status"] == "active" and out["cadence"] == "monthly" and out["next_run_at"]
    assert out["kind"] == "interval" and out["label"]
    # ENDPOINTS ONLY: creating a schedule must NOT run the tool yet
    assert db.query(Reminder).count() == 0, "must not execute — executor is the next phase"
    assert db.query(Schedule).filter(Schedule.feature_key.isnot(None)).count() == 1


def test_create_rejects_unknown_feature_and_bad_cadence():
    db = _mkdb()
    for bad in [{"feature_key": "no.such.tool"}, {"cadence": {"type": "fortnightly", "time": "09:00"}},
                {"cadence": {"type": "custom", "cron": "0 9 *"}}]:
        try:
            _create(db, **bad); assert False, f"should reject {bad}"
        except HTTPException as e:
            assert e.status_code in (400, 422)


# ── list separation from workflow schedules ───────────────────────────────────
def test_list_excludes_workflow_schedules():
    from app.models import Schedule
    from app.security import ulid
    from app.models import now as _now
    db = _mkdb()
    _create(db)
    db.add(Schedule(id=ulid("sch"), tenant_id="tnt_s", workflow_id="wf_1", kind="cron",
                    expression="0 9 * * 1", next_run_at=_now()))   # a workflow schedule
    db.commit()
    rows = FS.list_schedules(None, _P(), db)
    assert len(rows) == 1 and all(r["feature_key"] for r in rows)
    assert FS.list_schedules("paused", _P(), db) == []             # status filter


# ── edit / pause / resume / skip ──────────────────────────────────────────────
def test_edit_recomputes_next_run_on_cadence_change():
    db = _mkdb(); s = _create(db); db.commit()
    patched = FS.edit(s["id"], FS.SchedulePatch(cadence={"type": "daily", "time": "07:30"},
                                                instructions="keep it short"), _P(), db)
    assert patched["cadence"] == "daily" and patched["kind"] == "interval"
    assert patched["instructions"] == "keep it short"
    assert datetime.fromisoformat(patched["next_run_at"]).hour == 7


def test_pause_resume_skip():
    db = _mkdb(); s = _create(db); db.commit()
    assert FS.pause(s["id"], _P(), db)["status"] == "paused"
    assert FS.resume(s["id"], _P(), db)["status"] == "active"
    before = datetime.fromisoformat(FS.detail(s["id"], _P(), db)["next_run_at"])
    after = datetime.fromisoformat(FS.skip_next(s["id"], _P(), db)["next_run_at"])
    assert after > before, "skip-next moves the next run forward"


def test_runs_empty_until_executor():
    db = _mkdb(); s = _create(db); db.commit()
    assert FS.runs(s["id"], _P(), db) == []


def test_cancel_deletes_schedule_and_runs():
    from app.models import Schedule, ScheduleRun
    from app.security import ulid
    db = _mkdb(); s = _create(db); db.commit()
    db.add(ScheduleRun(id=ulid("run"), schedule_id=s["id"], tenant_id="tnt_s", status="success", summary="x"))
    db.commit()
    out = FS.cancel(s["id"], _P(), db); db.commit()
    assert out["ok"]
    assert db.query(Schedule).filter_by(id=s["id"]).count() == 0
    assert db.query(ScheduleRun).filter_by(schedule_id=s["id"]).count() == 0


def test_not_found_for_other_tenant_or_workflow_row():
    db = _mkdb()
    try:
        FS.detail("nope", _P(), db); assert False
    except HTTPException as e:
        assert e.status_code == 404


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
