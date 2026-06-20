"""
Agent Profile + plain-language weekly summary + light edits (Doc 26 Prompt K),
and simple plain-language agent creation (Prompt L).

The profile READS data we already have — the agent row, its tasks, and its
Operational-Memory slice (every successful tool call is one operational row with
{tool, agent, at}). The weekly summary is generated from that slice: counts by
tool, total actions, items waiting. Light edits (name, tone, hours, voice,
pause/resume) write directly — they're safe and non-breaking.

Simple creation infers ONLY safe tools from a plain description; sensitive tools
(email/whatsapp/handoff/browser/calendar writes) are never granted this way, and
every created agent inherits the locked approval gates (ARCHITECTURE §5).
"""
import json
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Principal, audit, current_user
from ..events import hub
from ..models import Agent, MemoryItem, Task, now
from ..security import ulid
from ..tools import TOOL_REGISTRY
from .. import assistant as _assistant  # noqa: F401  (import-time: registers all tools + packs)

router = APIRouter(tags=["agent-profile"])

# Which teammate "owns" each tool family — used to attribute operational memory
# to the right agent in the weekly summary, regardless of which actor logged it.
ROLE_PREFIXES = {
    "Scheduler": ("reminder.", "routine.", "deadline.", "calendar.", "finance.bill", "finance.track"),
    "Inbox": ("email.", "message.", "whatsapp.", "followup.", "contacts."),
    "Scribe": ("note.", "document.", "text.", "list."),
    "Finder": ("memory.", "contact.", "web.", "finance.budget", "finance.spending", "finance.report", "finance.categorize", "finance.import"),
    "Aria": ("task.", "briefing.", "roi.", "handoff."),
}
ROLE_DESC = {
    "Aria": "Understands what you need and assigns it to the right teammate.",
    "Scheduler": "Reminders, calendar and routines.", "Inbox": "Your messages and email.",
    "Scribe": "Writing, notes, documents and summaries.", "Finder": "Remembers things and looks them up.",
}
SENSITIVE_PREFIXES = ("email.", "whatsapp.", "handoff.", "browser.", "calendar.create",
                      "calendar.cancel", "calendar.update", "calendar.book", "contacts.sync")
WAITING = {"waiting", "needs_you", "needs_input", "blocked", "escalated"}
PROG = {"in_progress", "working", "executing"}


def agent_of_tool(tool_name: str) -> str:
    for role, prefixes in ROLE_PREFIXES.items():
        if tool_name.startswith(prefixes):
            return role
    return "Aria"


def safe_tools() -> set:
    """Tools a simple-created agent may be granted: no approval gate + not sensitive."""
    return {n for n, s in TOOL_REGISTRY.items()
            if s.approval == "none" and not n.startswith(SENSITIVE_PREFIXES)}


def infer_tools(description: str) -> list:
    d = (description or "").lower()
    picks = set()
    rules = [
        (("remind", "morning", "daily", "every day", "schedule", "routine"), ["reminder.create", "routine.create"]),
        (("deal", "discount", "price", "watch", "research", "compare", "news", "web", "site", "online", "look up"), ["web.search"]),
        (("note", "summary", "summarize", "write", "draft", "document", "report"), ["document.generate", "text.summarize"]),
        (("remember", "find", "recall", "track", "remind me of"), ["memory.write", "memory.search"]),
        (("bill", "subscription", "spend", "budget", "expense"), ["finance.track_subscription", "finance.budget_status"]),
    ]
    for kws, tools in rules:
        if any(k in d for k in kws):
            picks.update(tools)
    if not picks:
        picks = {"memory.search", "web.search"}     # a safe, useful default
    allowed = safe_tools()
    return sorted(t for t in picks if t in allowed)


def grants_for(tool_names) -> list:
    """The permission strings a set of tools needs (what the Actor.grants holds)."""
    return sorted({TOOL_REGISTRY[t].permission for t in tool_names if t in TOOL_REGISTRY})


# ── profile (Part 3) ──────────────────────────────────────────────────────────
def _op_rows(db, tenant_id, since):
    rows = (db.query(MemoryItem)
            .filter_by(tenant_id=tenant_id, memory_class="operational", source_type="agent_action")
            .filter(MemoryItem.created_at >= since).all())
    out = []
    for r in rows:
        try:
            b = json.loads(r.body)
            out.append({"tool": b.get("tool", ""), "summary": r.title,
                        "at": b.get("at") or (r.created_at.isoformat() if r.created_at else None)})
        except Exception:
            pass
    return out


def weekly_summary(db, tenant_id, agent_name):
    since = now() - timedelta(days=7)
    mine = [r for r in _op_rows(db, tenant_id, since) if agent_of_tool(r["tool"]) == agent_name]
    by_tool = {}
    for r in mine:
        by_tool[r["tool"]] = by_tool.get(r["tool"], 0) + 1
    waiting = (db.query(Task).filter_by(tenant_id=tenant_id)
               .filter(Task.status.in_(WAITING)).count()) if agent_name == "Aria" else 0
    # ~6 minutes saved per completed action (matches the ROI heuristic elsewhere)
    mins = len(mine) * 6
    phrase = _phrase(agent_name, by_tool, len(mine), mins, waiting)
    return {"actions": len(mine), "by_tool": by_tool, "minutes_saved": mins,
            "waiting": waiting, "phrase": phrase}


def _phrase(name, by_tool, total, mins, waiting):
    if total == 0:
        return f"{name} hasn't had anything to do this week yet."
    bits = ", ".join(f"{c} × {t.split('.')[-1].replace('_', ' ')}" for t, c in sorted(by_tool.items(), key=lambda x: -x[1])[:3])
    tail = f" {waiting} waiting for you." if waiting else ""
    return f"This week {name} handled {total} thing{'s' if total != 1 else ''} ({bits}) — about {mins} minutes saved.{tail}"


def _agent(db, agent_id, p):
    a = db.get(Agent, agent_id)
    if not a or a.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Agent not found"})
    return a


@router.get("/agents/{agent_id}/profile")
def profile(agent_id: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    a = _agent(db, agent_id, p)
    tasks = db.query(Task).filter_by(tenant_id=p.tenant_id, assignee_agent_id=a.id).all()
    doing = next((t.title for t in tasks if t.status in PROG), None)
    recent = sorted(_op_rows(db, p.tenant_id, now() - timedelta(days=30)),
                    key=lambda r: r["at"] or "", reverse=True)
    recent = [r for r in recent if agent_of_tool(r["tool"]) == a.name][:12]
    sched = a.schedule or {}
    return {
        "id": a.id, "name": a.name, "role": a.designation or ROLE_DESC.get(a.name, "Assistant"),
        "description": a.description or ROLE_DESC.get(a.name, ""), "status": a.status,
        "voice_id": a.voice_id, "is_ceo": a.is_ceo,
        "tone": sched.get("tone", "friendly"), "hours": sched.get("hours", "anytime"),
        "doing_now": doing, "recent": recent, "this_week": weekly_summary(db, p.tenant_id, a.name),
    }


class LightEdit(BaseModel):
    name: str | None = None
    tone: str | None = None
    hours: str | None = None
    voice_id: str | None = None


@router.post("/agents/{agent_id}/light-edit")
def light_edit(agent_id: str, body: LightEdit, p: Principal = Depends(current_user),
               db: Session = Depends(get_db)):
    """Everyone-allowed edits: name, tone, working hours, voice. Non-breaking, direct."""
    a = _agent(db, agent_id, p)
    if body.name:
        a.name = body.name
    if body.voice_id:
        a.voice_id = body.voice_id
    sched = dict(a.schedule or {})
    if body.tone:
        sched["tone"] = body.tone
    if body.hours:
        sched["hours"] = body.hours
    a.schedule = sched
    audit(db, plane="local", actor=f"user:{p.user_id}", action="agent.light_edit",
          target=a.id, tenant_id=p.tenant_id)
    db.commit()
    return {"ok": True, "name": a.name, "tone": sched.get("tone"), "hours": sched.get("hours"), "voice_id": a.voice_id}


# ── simple creation (Part 4.1) ────────────────────────────────────────────────
class Propose(BaseModel):
    description: str
    name: str | None = None
    cadence: str | None = None


@router.post("/agents/simple/propose")
def propose(body: Propose, p: Principal = Depends(current_user)):
    """Aria's read-back: name, plain description, inferred SAFE tools, schedule."""
    tools = infer_tools(body.description)
    name = (body.name or "New Agent").strip()
    return {"name": name, "description": body.description, "cadence": body.cadence or "on demand",
            "tools": tools, "tool_labels": [TOOL_REGISTRY[t].description for t in tools],
            "readback": f"I'll create “{name}” — {body.description}. "
                        f"It can {', '.join(t.split('.')[-1].replace('_', ' ') for t in tools) or 'use safe tools'}, "
                        f"working {body.cadence or 'on demand'}. Anything sensitive will ask you first."}


@router.post("/agents/simple")
def create_simple(body: Propose, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Create a plain-language agent. Server-side enforces SAFE tools only +
    locked approval gates (a user can't grant powerful tools this way)."""
    tools = infer_tools(body.description)                  # safe-filtered server-side
    a = Agent(id=ulid("agt"), tenant_id=p.tenant_id, name=(body.name or "New Agent").strip(),
              designation="Custom agent", description=body.description,
              objectives=[body.description], model_tier="local",
              tools=tools, skills=[], status="idle", voice_id="piper-female-1",
              permissions={"spend_limit": 0, "external_send": "approval_required"},
              schedule={"cadence": body.cadence or "on demand"})
    db.add(a)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="agent.create_simple",
          target=a.id, tenant_id=p.tenant_id, meta={"tools": tools})
    db.commit()
    hub.emit(p.tenant_id, "agent.status", {"agent_id": a.id, "status": "idle", "name": a.name, "event": "created"})
    return {"id": a.id, "name": a.name, "tools": tools, "grants": grants_for(tools),
            "message": f"“{a.name}” is ready — find it on your Agent Map."}
