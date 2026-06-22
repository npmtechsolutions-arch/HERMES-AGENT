"""
Feature schedules (Doc 29 §5.1b) — run any of the 23 tools on a cadence. A
feature schedule is the SAME tool the live mode runs, only the trigger differs
(ARCHITECTURE §3/§4: reuse the scheduler engine + tool contract, no new engine).

This phase is ENDPOINTS ONLY — create / list / edit / pause / resume / skip-next
/ run-history. The executor that actually fires due schedules (→ call_tool, with
retries + approval-park per §5/§7) is the NEXT phase. Until then these rows store
intent and won't execute.

Path is /feature-schedules (not /schedules) because workflows.py already owns
/schedules for workflow schedules — avoid the collision.
"""
import calendar
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Principal, audit, current_user
from ..models import Schedule, ScheduleRun, now
from ..security import ulid
from ..tools import TOOL_REGISTRY
from .. import assistant as _assistant  # noqa: F401  (import-time: registers all tools)
from .agents_profile import agent_of_tool

router = APIRouter(tags=["feature-schedules"])

CADENCES = {"daily", "weekly", "monthly", "yearly", "custom"}


# ── cadence → next run time (pure helpers) ───────────────────────────────────
def _utc(dt):
    """Normalize to UTC for safe compares. SQLite returns tz-naive (assume UTC);
    Postgres returns tz-aware in the session zone (convert). Must NOT just strip
    tzinfo — an IST wall-clock would mis-compare against a UTC now()."""
    if not dt:
        return dt
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _parse_time(s):
    try:
        h, m = str(s or "09:00").split(":")[:2]
        return max(0, min(23, int(h))), max(0, min(59, int(m)))
    except Exception:
        return 9, 0


def _add_months(dt, n):
    month = dt.month - 1 + n
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _set_day(dt, day):
    return dt.replace(day=min(int(day), calendar.monthrange(dt.year, dt.month)[1]))


def _cron_field(expr, lo, hi):
    """Parse one cron field into the set of allowed ints. Supports *, a, a-b,
    a,b, */n, a-b/n."""
    vals = set()
    for part in str(expr).split(","):
        step = 1
        rng = part
        if "/" in part:
            rng, step = part.split("/", 1)
            step = int(step)
        if rng == "*":
            start, end = lo, hi
        elif "-" in rng:
            a, b = rng.split("-", 1)
            start, end = int(a), int(b)
        else:
            start = end = int(rng)
        if start < lo or end > hi or step < 1:
            raise ValueError(f"cron field out of range: {part}")
        vals.update(range(start, end + 1, step))
    return vals


def cron_next(expr: str, after: datetime) -> datetime:
    """Next datetime strictly after `after` matching a 5-field cron
    (min hour day month weekday). Weekday: 0/7=Sunday, 1=Mon … 6=Sat (standard
    cron). Day-of-month AND day-of-week follow Vixie semantics: if BOTH are
    restricted, a day matches when EITHER matches; if one is '*', use the other."""
    fields = str(expr).split()
    if len(fields) != 5:
        raise ValueError("cron must have 5 fields")
    minute = _cron_field(fields[0], 0, 59)
    hour = _cron_field(fields[1], 0, 23)
    dom = _cron_field(fields[2], 1, 31)
    month = _cron_field(fields[3], 1, 12)
    dow = _cron_field(fields[4], 0, 7)
    if 7 in dow:
        dow = (dow - {7}) | {0}
    dom_r, dow_r = fields[2] != "*", fields[4] != "*"

    def day_ok(t):
        dm = t.day in dom
        dw = ((t.weekday() + 1) % 7) in dow      # python Mon=0..Sun=6 → cron Sun=0..Sat=6
        if dom_r and dow_r:
            return dm or dw
        if dom_r:
            return dm
        if dow_r:
            return dw
        return True

    t = (after + timedelta(minutes=1)).replace(second=0, microsecond=0)
    end = t + timedelta(days=366 * 5)            # bound (covers Feb-29 quadrennials)
    while t < end:
        if t.month not in month or not day_ok(t):
            t = (t + timedelta(days=1)).replace(hour=0, minute=0)   # skip the whole day
            continue
        if t.hour in hour and t.minute in minute:
            return t
        t += timedelta(minutes=1)
    raise ValueError(f"no cron match within horizon for '{expr}'")


def next_run(spec: dict, base_now: datetime) -> datetime:
    """The next future fire time for a cadence spec, strictly after base_now."""
    typ = spec.get("type")
    h, m = _parse_time(spec.get("time"))
    base = base_now.replace(hour=h, minute=m, second=0, microsecond=0)
    if typ == "daily":
        return base if base > base_now else base + timedelta(days=1)
    if typ == "weekly":
        wd = int(spec.get("weekday", base_now.weekday()))
        cand = base + timedelta(days=(wd - base_now.weekday()) % 7)
        return cand if cand > base_now else cand + timedelta(days=7)
    if typ == "monthly":
        cand = _set_day(base, spec.get("day", min(base_now.day, 28)))
        return cand if cand > base_now else _set_day(_add_months(base, 1), spec.get("day", min(base_now.day, 28)))
    if typ == "yearly":
        month = int(spec.get("month", base_now.month))
        day = min(int(spec.get("day", base_now.day)), calendar.monthrange(base_now.year, month)[1])
        cand = base.replace(month=month, day=day)
        return cand if cand > base_now else cand.replace(year=cand.year + 1)
    if typ == "custom":
        return cron_next(spec.get("cron"), base_now)
    return base_now + timedelta(days=1)


def _validate(feature_key: str, spec: dict):
    if feature_key not in TOOL_REGISTRY:
        raise HTTPException(400, detail={"code": "UNKNOWN_FEATURE",
                                         "message": f"'{feature_key}' is not a known feature."})
    typ = (spec or {}).get("type")
    if typ not in CADENCES:
        raise HTTPException(422, detail={"code": "VALIDATION_ERROR",
                                         "message": f"cadence.type must be one of {sorted(CADENCES)}."})
    if typ == "custom" and len((spec.get("cron") or "").split()) != 5:
        raise HTTPException(422, detail={"code": "VALIDATION_ERROR",
                                         "message": "Custom cadence needs a 5-field cron, e.g. '0 9 * * 1'."})


def _kind_expr(spec: dict):
    typ = spec.get("type")
    return ("cron", spec.get("cron")) if typ == "custom" else ("interval", typ)


def _dto(s: Schedule):
    return {
        "id": s.id, "feature_key": s.feature_key, "label": s.label, "agent": s.agent,
        "params": s.params or {}, "instructions": s.instructions,
        "cadence": s.cadence, "cadence_spec": s.cadence_spec or {},
        "kind": s.kind, "expression": s.expression, "timezone": s.timezone,
        "status": s.status, "consecutive_failures": s.consecutive_failures,
        "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None,
        "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
        "last_status": s.last_status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _get(db, sid, p) -> Schedule:
    s = db.get(Schedule, sid)
    if not s or s.tenant_id != p.tenant_id or not s.feature_key:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Schedule not found."})
    return s


# ── endpoints ─────────────────────────────────────────────────────────────────
class ScheduleIn(BaseModel):
    feature_key: str
    params: dict = {}
    cadence: dict                       # {type, time, weekday?, day?, month?, cron?}
    instructions: str | None = None
    label: str | None = None


@router.post("/feature-schedules")
def create(body: ScheduleIn, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    _validate(body.feature_key, body.cadence)
    kind, expr = _kind_expr(body.cadence)
    s = Schedule(id=ulid("sch"), tenant_id=p.tenant_id, workflow_id=None,
                 feature_key=body.feature_key, user_id=p.user_id, params=body.params or {},
                 instructions=body.instructions, label=body.label or TOOL_REGISTRY[body.feature_key].description,
                 agent=agent_of_tool(body.feature_key), cadence=body.cadence.get("type"),
                 cadence_spec=body.cadence, kind=kind, expression=expr, status="active",
                 next_run_at=next_run(body.cadence, now()))
    db.add(s)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="feature_schedule.create",
          target=s.id, tenant_id=p.tenant_id, meta={"feature": body.feature_key, "cadence": s.cadence})
    db.commit()
    return _dto(s)


@router.get("/feature-schedules")
def list_schedules(status: str | None = None, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(Schedule).filter(Schedule.tenant_id == p.tenant_id, Schedule.feature_key.isnot(None))
    if status:
        q = q.filter(Schedule.status == status)
    return [_dto(s) for s in q.order_by(Schedule.next_run_at).all()]


@router.get("/feature-schedules/{sid}")
def detail(sid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    return _dto(_get(db, sid, p))


class SchedulePatch(BaseModel):
    params: dict | None = None
    instructions: str | None = None
    cadence: dict | None = None
    label: str | None = None


@router.patch("/feature-schedules/{sid}")
def edit(sid: str, body: SchedulePatch, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    s = _get(db, sid, p)
    if body.params is not None:
        s.params = body.params
    if body.instructions is not None:
        s.instructions = body.instructions
    if body.label is not None:
        s.label = body.label
    if body.cadence is not None:
        _validate(s.feature_key, body.cadence)
        s.cadence_spec = body.cadence
        s.cadence = body.cadence.get("type")
        s.kind, s.expression = _kind_expr(body.cadence)
        s.next_run_at = next_run(body.cadence, now())       # recompute on cadence change
    audit(db, plane="local", actor=f"user:{p.user_id}", action="feature_schedule.update",
          target=s.id, tenant_id=p.tenant_id)
    db.commit()
    return _dto(s)


@router.post("/feature-schedules/{sid}/pause")
def pause(sid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    s = _get(db, sid, p); s.status = "paused"; db.commit()
    return _dto(s)


@router.post("/feature-schedules/{sid}/resume")
def resume(sid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    s = _get(db, sid, p)
    s.status = "active"
    if not s.next_run_at or _utc(s.next_run_at) <= _utc(now()):       # don't resume into the past
        s.next_run_at = next_run(s.cadence_spec or {"type": s.cadence}, now())
    db.commit()
    return _dto(s)


@router.post("/feature-schedules/{sid}/skip-next")
def skip_next(sid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    s = _get(db, sid, p)
    base = s.next_run_at or now()
    s.next_run_at = next_run(s.cadence_spec or {"type": s.cadence}, base)   # the run AFTER the current one
    db.commit()
    return _dto(s)


@router.delete("/feature-schedules/{sid}")
def cancel(sid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Cancel a scheduled task for good — removes it and its run history."""
    s = _get(db, sid, p)
    db.query(ScheduleRun).filter_by(schedule_id=sid).delete()
    db.delete(s)
    db.commit()
    return {"ok": True, "id": sid, "message": "Scheduled task canceled."}


@router.get("/feature-schedules/{sid}/runs")
def runs(sid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    _get(db, sid, p)
    rows = (db.query(ScheduleRun).filter_by(schedule_id=sid, tenant_id=p.tenant_id)
            .order_by(ScheduleRun.at.desc()).all())
    return [{"id": r.id, "status": r.status, "summary": r.summary, "error": r.error,
             "retries": r.retries, "at": r.at.isoformat() if r.at else None} for r in rows]
