"""
The feature-schedule EXECUTOR (Doc 29 §5.1b runner). Fires due schedules on their
cadence by calling the SAME tool the live mode calls — one execution path, two
triggers (ARCHITECTURE §3/§4, Part 5.3). No second code path, no new engine.

Safety, enforced in code (not convention):
  • §5 approval gates — a gated tool (money / new-contact / destructive) PARKS an
    Approval and does NOT execute autonomously. It runs only after the human
    approves (resume_after_approval, called from the decide endpoint).
  • §7 failure handling — call_tool already does bounded transient retries; the
    executor escalates after MAX_FAILS consecutive hard failures by PAUSING the
    schedule and surfacing it (never an infinite silent retry loop).
  • One ScheduleRun row per run (success | needs_approval | failed).
"""
import os
import threading
import time

from .events import hub
from .models import Approval, Schedule, ScheduleRun, Tenant, now as _now
from .routers.feature_schedules import _utc, cron_next, next_run
from .security import ulid
from .tools import Actor, ToolContext, call_tool

MAX_FAILS = 3        # consecutive hard failures → pause + surface (Doc 29 #8)


def _owner(db, tenant_id):
    t = db.get(Tenant, tenant_id)
    return t.owner_user_id if t else None


def _advance(s: Schedule, fired_at):
    spec = s.cadence_spec or {"type": s.cadence}
    if spec.get("type") == "custom":
        s.next_run_at = cron_next(spec.get("cron") or s.expression, fired_at)
    else:
        s.next_run_at = next_run(spec, fired_at)


def _record(db, s, run_id, status, summary, error, retries=0):
    db.add(ScheduleRun(id=run_id, schedule_id=s.id, tenant_id=s.tenant_id,
                       status=status, summary=summary, error=error, retries=retries))


def _park_approval(db, s, params, run_id):
    """§5 — a scheduled run that hits a gate parks for the human instead of failing."""
    db.add(Approval(
        id=ulid("apv"), tenant_id=s.tenant_id, action_summary=s.label or s.feature_key,
        payload={"schedule_id": s.id, "feature_key": s.feature_key, "params": params,
                 "run_id": run_id, "user_id": s.user_id},
        rule_id="SCHED-GATE", current_tier="human", state="pending"))
    try:
        hub.emit(s.tenant_id, "approval.created",
                 {"schedule_id": s.id, "summary": s.label or s.feature_key})
    except Exception:
        pass


def _run_one(db, s: Schedule, now):
    user_id = s.user_id or _owner(db, s.tenant_id)
    ctx = ToolContext(actor=Actor(tenant_id=s.tenant_id, user_id=user_id,
                                  agent_id=s.agent or "Aria", grants={"*"}), db=db)
    params = dict(s.params or {})
    run_id = ulid("run")
    r = call_tool(s.feature_key, ctx, **params)   # SAME tool live mode calls
    s.last_run_at = now

    if r.ok:
        _record(db, s, run_id, "success", r.summary, None)
        s.consecutive_failures = 0
        s.last_status = "success"
        _advance(s, now)
        return {"schedule": s.id, "status": "success"}

    if r.error == "user_input_needed":            # §5 gate → park, do NOT execute
        _park_approval(db, s, params, run_id)
        _record(db, s, run_id, "needs_approval", r.summary, None)
        s.last_status = "needs_approval"
        _advance(s, now)
        return {"schedule": s.id, "status": "needs_approval"}

    # hard failure (§7) — escalate after MAX_FAILS, never loop forever
    _record(db, s, run_id, "failed", r.summary, r.error)
    s.consecutive_failures = (s.consecutive_failures or 0) + 1
    s.last_status = "failed"
    if s.consecutive_failures >= MAX_FAILS:
        s.status = "paused"
        try:
            hub.emit(s.tenant_id, "schedule.escalated",
                     {"schedule_id": s.id, "summary": s.label or s.feature_key,
                      "failures": s.consecutive_failures})
        except Exception:
            pass
    else:
        _advance(s, now)
    return {"schedule": s.id, "status": "failed", "consecutive_failures": s.consecutive_failures}


def run_due_schedules(db, *, now=None):
    """Run every active feature schedule whose next_run_at is due. Caller commits."""
    now = now or _now()
    rows = (db.query(Schedule)
            .filter(Schedule.feature_key.isnot(None), Schedule.status == "active").all())
    due = [s for s in rows if s.next_run_at and _utc(s.next_run_at) <= _utc(now)]
    return [_run_one(db, s, now) for s in due]


def resume_after_approval(db, approval: Approval):
    """Continue a parked scheduled run once the human approves (§5). Called from
    the approvals decide endpoint. Returns the ToolResult, or None if not ours."""
    pl = approval.payload or {}
    fk = pl.get("feature_key")
    if not fk:
        return None
    s = db.get(Schedule, pl.get("schedule_id"))
    user_id = pl.get("user_id") or (s.user_id if s else None) or _owner(db, approval.tenant_id)
    ctx = ToolContext(actor=Actor(tenant_id=approval.tenant_id, user_id=user_id,
                                  agent_id=(s.agent if s else "Aria"), grants={"*"}),
                      db=db, approved=True)
    r = call_tool(fk, ctx, **(pl.get("params") or {}))
    run = db.get(ScheduleRun, pl.get("run_id"))
    status = "success" if r.ok else "failed"
    if run:
        run.status = status
        run.summary = r.summary
        run.error = None if r.ok else r.error
    if s:
        s.last_status = status
        if r.ok:
            s.consecutive_failures = 0
    return r


# ── background trigger (daemon thread; the executor's only "two triggers" peer) ─
_started = False


def start_scheduler(interval=30):
    """Start the background tick. No-op if HERMUS_SCHEDULER=0 or already running."""
    global _started
    if _started or os.getenv("HERMUS_SCHEDULER", "1") == "0":
        return
    _started = True
    threading.Thread(target=_loop, args=(interval,), daemon=True).start()


def _loop(interval):
    from .database import SessionLocal
    while True:
        try:
            db = SessionLocal()
            try:
                run_due_schedules(db)
                db.commit()
            finally:
                db.close()
        except Exception as e:                    # a bad tick must never kill the loop
            print(f"[scheduler] tick error: {e}")
        time.sleep(interval)
