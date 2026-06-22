"""
Tests for the feature-schedule EXECUTOR (Doc 29 §5.1b runner). Two areas the
reviewer flagged to scrutinise:
  1. The hand-rolled cron parser — tested hard (steps, ranges, lists, weekday
     mapping, day rollover).
  2. The safety path — a gated tool PARKS for approval and does NOT execute
     autonomously; it runs only after approval.
Plus: due schedules fire the REAL tool, next_run advances, paused/not-due skip,
repeated failure escalates (pause after 3), one ScheduleRun per run.

Run:  python -m pytest tests/test_scheduler_exec.py -q
Or:   python tests/test_scheduler_exec.py
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["HERMUS_SCHEDULER"] = "0"   # never start the background thread in tests

from app import scheduler_exec as EX  # noqa: E402
from app.routers import feature_schedules as FS  # noqa: E402
from app.routers.feature_schedules import cron_next  # noqa: E402

UTC = timezone.utc


def _mkdb():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def _sched(db, feature_key, params, *, due=True, cadence=None, label="t"):
    from app.models import Schedule, now as _n
    from app.security import ulid
    spec = cadence or {"type": "daily", "time": "09:00"}
    s = Schedule(id=ulid("sch"), tenant_id="tnt_e", user_id="usr_e", feature_key=feature_key,
                 params=params, label=label, agent="Scheduler", cadence=spec["type"],
                 cadence_spec=spec, kind="interval", expression=spec["type"], status="active",
                 next_run_at=(_n() - timedelta(minutes=1)) if due else (_n() + timedelta(days=1)))
    db.add(s); db.commit()
    return s


# ── CRON PARSER (the riskiest piece) ──────────────────────────────────────────
def test_cron_every_15_minutes():
    t = datetime(2026, 6, 18, 10, 7, tzinfo=UTC)
    n = cron_next("*/15 * * * *", t)
    assert n.minute == 15 and n.hour == 10 and n.second == 0


def test_cron_9am_monday():
    # from a Sunday — must land on Monday 09:00 (cron weekday 1 = Monday)
    sun = datetime(2026, 6, 21, 10, 0, tzinfo=UTC)
    assert sun.weekday() == 6                      # sanity: 2026-06-21 is a Sunday
    n = cron_next("0 9 * * 1", sun)
    assert n.weekday() == 0 and n.hour == 9 and n.minute == 0 and n.day == 22


def test_cron_daily_rolls_to_tomorrow():
    t = datetime(2026, 6, 18, 10, 0, tzinfo=UTC)
    n = cron_next("0 9 * * *", t)                  # 9am already passed today
    assert n.day == 19 and n.hour == 9


def test_cron_ranges_and_lists():
    t = datetime(2026, 6, 18, 20, 0, tzinfo=UTC)
    assert cron_next("0 9-17 * * *", t).hour == 9 and cron_next("0 9-17 * * *", t).day == 19
    n = cron_next("0 0 1,15 * *", t)               # next 1st or 15th of a month
    assert n.day in (1, 15) and n.hour == 0
    assert cron_next("0 0 29 2 *", t).month == 2 and cron_next("0 0 29 2 *", t).day == 29  # Feb 29 (leap)


def test_cron_sunday_zero_and_seven_equivalent():
    t = datetime(2026, 6, 18, 0, 0, tzinfo=UTC)
    assert cron_next("0 0 * * 0", t).weekday() == 6 and cron_next("0 0 * * 7", t).weekday() == 6


# ── EXECUTOR fires the REAL tool ──────────────────────────────────────────────
def test_due_schedule_creates_a_real_reminder_and_advances():
    from app.models import Reminder, ScheduleRun, now as _n
    db = _mkdb()
    s = _sched(db, "reminder.create", {"text": "pay rent", "due_at": "2026-07-01T09:00:00+00:00"})
    old_next = s.next_run_at
    out = EX.run_due_schedules(db, now=_n()); db.commit()
    assert out and out[0]["status"] == "success"
    assert db.query(Reminder).filter_by(tenant_id="tnt_e").count() == 1, "the SAME tool live mode runs"
    run = db.query(ScheduleRun).filter_by(schedule_id=s.id).one()
    assert run.status == "success"
    assert s.next_run_at > old_next and s.consecutive_failures == 0 and s.last_status == "success"


def test_not_due_and_paused_are_skipped():
    from app.models import Reminder, now as _n
    db = _mkdb()
    _sched(db, "reminder.create", {"text": "later", "due_at": "2026-07-01T09:00:00+00:00"}, due=False)
    paused = _sched(db, "reminder.create", {"text": "paused", "due_at": "2026-07-01T09:00:00+00:00"})
    paused.status = "paused"; db.commit()
    EX.run_due_schedules(db, now=_n()); db.commit()
    assert db.query(Reminder).count() == 0


# ── SAFETY: a gated tool parks for approval and does NOT execute ───────────────
def test_gated_tool_parks_approval_and_does_not_execute():
    from app.models import Approval, MemoryItem, ScheduleRun, now as _n
    from app.security import ulid
    db = _mkdb()
    mem = MemoryItem(id=ulid("mem"), tenant_id="tnt_e", memory_class="personal",
                     title="secret", source_type="note", body="x", tier="hot")
    db.add(mem); db.commit()
    # memory.forget is approval=required (destructive, §5)
    s = _sched(db, "memory.forget", {"id": mem.id})
    EX.run_due_schedules(db, now=_n()); db.commit()

    apv = db.query(Approval).filter_by(tenant_id="tnt_e", state="pending").one()
    assert apv.payload["feature_key"] == "memory.forget" and apv.rule_id == "SCHED-GATE"
    assert db.query(ScheduleRun).filter_by(status="needs_approval").count() == 1
    assert db.get(MemoryItem, mem.id).tier == "hot", "MUST NOT delete autonomously — parked, not run"

    # now the human approves → it runs immediately (resume hook)
    r = EX.resume_after_approval(db, apv); db.commit()
    assert r.ok and db.get(MemoryItem, mem.id).tier == "deleted", "runs only after approval"
    assert db.query(ScheduleRun).filter_by(schedule_id=s.id, status="success").count() == 1


# ── §7 failure escalation: pause after MAX_FAILS, no infinite loop ────────────
def test_repeated_failure_pauses_after_three():
    from app.models import Schedule, ScheduleRun, now as _n
    db = _mkdb()
    # missing required `source` → validation error → hard fail every run
    s = _sched(db, "text.summarize", {})
    for _ in range(EX.MAX_FAILS):
        s = db.get(Schedule, s.id)
        s.next_run_at = _n() - timedelta(minutes=1)       # make it due again
        s.status = "active"; db.commit()
        EX.run_due_schedules(db, now=_n()); db.commit()
    s = db.get(Schedule, s.id)
    assert s.consecutive_failures >= EX.MAX_FAILS and s.status == "paused", "escalated, not looping"
    assert db.query(ScheduleRun).filter_by(schedule_id=s.id, status="failed").count() == EX.MAX_FAILS


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
