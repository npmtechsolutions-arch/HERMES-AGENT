"""
Doc 27 — the user's-eye dashboard layer. Surfaces what the engine already does:
- Work Summary (Part 8): the value/renewal view — work done, hours saved, trends.
- Agent Activity (Part 4.4): every agent action with ✅ / ⚠️ / ❌ markers, filterable.
- My Activity (Part 6): what the USER did — commands, decisions, files, agents made.

All read existing data (operational memory, audit log, ROI). No engine change.
"""
import json
from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Principal, current_user
from ..models import Agent, AuditLog, MemoryItem, Reminder, RoiEntry, Task, now
from .agents_profile import agent_of_tool, ROLE_DESC, weekly_summary, _op_rows

router = APIRouter(tags=["journey"])

RATE_PER_HOUR = 500     # ₹/hr, matches the ROI methodology elsewhere
MIN_PER_ACTION = 6      # conservative minutes saved per automated action


def _naive(dt):
    """SQLite returns tz-naive datetimes, Postgres tz-aware — normalize for compares."""
    return dt.replace(tzinfo=None) if (dt and dt.tzinfo) else dt


def _op_actions(db, tenant_id, since):
    rows = (db.query(MemoryItem)
            .filter_by(tenant_id=tenant_id, memory_class="operational", source_type="agent_action")
            .filter(MemoryItem.created_at >= since).all())
    out = []
    for r in rows:
        try:
            b = json.loads(r.body)
            out.append({"tool": b.get("tool", ""), "agent": agent_of_tool(b.get("tool", "")),
                        "summary": r.title, "at": r.created_at})
        except Exception:
            pass
    return out


@router.get("/work-summary")
def work_summary(range: str = "week", p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Part 8 — total work by agents, value (hours saved), and trends."""
    days = {"week": 7, "month": 30, "all": 3650}.get(range, 7)
    since = now() - timedelta(days=days)
    prev_since = since - timedelta(days=days)
    acts = _op_actions(db, p.tenant_id, since)
    prev = _op_actions(db, p.tenant_id, prev_since)
    prev = [a for a in prev if a["at"] and _naive(a["at"]) < _naive(since)]

    by_agent, by_area, by_day = {}, {}, {}
    for a in acts:
        by_agent[a["agent"]] = by_agent.get(a["agent"], 0) + 1
        area = a["tool"].split(".")[0]
        by_area[area] = by_area.get(area, 0) + 1
        day = a["at"].strftime("%Y-%m-%d") if a["at"] else "?"
        by_day[day] = by_day.get(day, 0) + 1

    roi = db.query(RoiEntry).filter(RoiEntry.tenant_id == p.tenant_id, RoiEntry.at >= since).all()
    roi_minutes = sum(float(r.value_minutes or 0) for r in roi)
    after_hours = sum(1 for r in roi if r.after_hours)
    total = len(acts)
    minutes_saved = round(total * MIN_PER_ACTION + roi_minutes)
    hours_saved = round(minutes_saved / 60, 1)

    most_active = max(by_agent.items(), key=lambda x: x[1])[0] if by_agent else None
    busiest_area = max(by_area.items(), key=lambda x: x[1])[0] if by_area else None
    delta = total - len(prev)
    trend = ("up" if delta > 0 else "down" if delta < 0 else "flat")

    return {
        "range": range, "total_actions": total, "by_agent": by_agent, "by_area": by_area,
        "by_day": dict(sorted(by_day.items())),
        "value": {"hours_saved": hours_saved, "minutes_saved": minutes_saved,
                  "after_hours": after_hours, "money_value_inr": int(hours_saved * RATE_PER_HOUR)},
        "trends": {"this_period": total, "last_period": len(prev), "delta": delta, "direction": trend,
                   "most_active_agent": most_active, "busiest_area": busiest_area},
        "headline": _headline(total, hours_saved, most_active, range),
    }


def _headline(total, hours, agent, range):
    if total == 0:
        return f"No automated work yet this {range} — give your assistant something to do."
    who = f" {agent} was busiest." if agent else ""
    return f"This {range}: {total} thing{'s' if total != 1 else ''} handled · ~{hours} hours saved.{who}"


@router.get("/team/overview")
def agents_overview(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Part 4 (Action Summary) — every agent with what it's doing now, what's
    scheduled, recent actions, and this week's stats. One screen, full picture."""
    agents = db.query(Agent).filter_by(tenant_id=p.tenant_id).all()
    tasks = db.query(Task).filter_by(tenant_id=p.tenant_id).all()
    reminders = db.query(Reminder).filter_by(tenant_id=p.tenant_id, status="active").count()
    recent_all = sorted(_op_rows(db, p.tenant_id, now() - timedelta(days=14)),
                        key=lambda r: r["at"] or "", reverse=True)
    PROG_S = {"in_progress", "working", "executing", "planning"}
    QUEUE_S = {"queued", "scheduled", "pending", "todo", "planning"}
    out = []
    for a in agents:
        mine_tasks = [t for t in tasks if t.assignee_agent_id == a.id]
        doing = next((t.title for t in mine_tasks if t.status in PROG_S), None)
        scheduled = [t.title for t in mine_tasks if t.status in QUEUE_S]
        # Scheduler also "owns" active reminders
        sched_count = len(scheduled) + (reminders if a.name == "Scheduler" else 0)
        recent = [r for r in recent_all if agent_of_tool(r["tool"]) == a.name][:5]
        out.append({
            "id": a.id, "name": a.name, "role": a.designation or ROLE_DESC.get(a.name, "Assistant"),
            "status": a.status, "is_ceo": a.is_ceo, "doing_now": doing,
            "scheduled_count": sched_count, "scheduled": scheduled[:5],
            "recent": recent, "this_week": weekly_summary(db, p.tenant_id, a.name),
        })
    # CEO (Aria) first, then by busyness
    out.sort(key=lambda x: (not x["is_ceo"], -x["this_week"]["actions"]))
    return {"agents": out, "totals": {"agents": len(agents),
            "working": sum(1 for a in agents if a.status == "working"),
            "scheduled": reminders}}


@router.get("/agent-activity")
def agent_activity(agent: str | None = None, status: str | None = None, limit: int = 60,
                   p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Part 4.4 — agent actions with success/failure markers, filterable."""
    rows = (db.query(AuditLog).filter(AuditLog.chain_key == p.tenant_id,
                                      AuditLog.action == "assistant.action")
            .order_by(AuditLog.id.desc()).limit(400).all())
    out = []
    for r in rows:
        meta = r.meta or {}
        tool = meta.get("tool", "")
        ok = meta.get("ok", True)
        ag = agent_of_tool(tool) if tool else "Aria"
        mark = "success" if ok else "failed"
        if agent and ag != agent:
            continue
        if status and mark != status:
            continue
        out.append({"id": r.id, "agent": ag, "tool": tool, "summary": r.target,
                    "marker": mark, "at": r.at.isoformat() if r.at else None,
                    "why": f"{ag} ran {tool or 'an action'} because you asked."})
    return {"activity": out[:limit]}


@router.get("/my-activity")
def my_activity(limit: int = 80, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Part 6 — what the USER did: commands, approvals, files, agents created."""
    rows = (db.query(AuditLog).filter(AuditLog.chain_key == p.tenant_id,
                                      AuditLog.actor.like("user:%"))
            .order_by(AuditLog.id.desc()).limit(limit).all())
    LABEL = {"user.command": "Asked", "approval.decided": "Decided", "connection.disconnect": "Disconnected",
             "agent.create_simple": "Created an agent", "agent.light_edit": "Edited an agent",
             "agent.advanced_publish": "Published an agent edit", "agent.advanced_revert": "Reverted an agent",
             "memory.ingest": "Added to memory"}
    out = []
    for r in rows:
        meta = r.meta or {}
        out.append({"id": r.id, "kind": LABEL.get(r.action, r.action.replace("_", " ").replace(".", " ").title()),
                    "detail": r.target, "tool": meta.get("tool"),
                    "at": r.at.isoformat() if r.at else None})
    return {"activity": out}
