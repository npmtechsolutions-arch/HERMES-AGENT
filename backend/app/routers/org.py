"""Organization: departments, agents, org chart, hire wizard, performance."""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Principal, audit, current_user
from ..events import hub
from ..models import (Agent, AgentPerformance, AuditLog, BusMessage, BusThread,
                      Department, Plan, Subscription, Task)
from ..security import ulid

router = APIRouter(tags=["organization"])


def agent_dto(a: Agent):
    return {
        "id": a.id, "name": a.name, "designation": a.designation,
        "department_id": a.department_id, "description": a.description,
        "objectives": a.objectives or [], "model_id": a.model_id,
        "permissions": a.permissions or {}, "kpis": a.kpis or [],
        "schedule": a.schedule or {}, "reporting_manager_id": a.reporting_manager_id,
        "status": a.status, "voice_id": a.voice_id, "is_ceo": a.is_ceo,
        "skills": a.skills or [], "tools": a.tools or [],
        "model_tier": a.model_tier or "local",
    }


def _plan_limits(db, tenant_id):
    sub = db.query(Subscription).filter_by(tenant_id=tenant_id).first()
    plan = db.get(Plan, sub.plan_id) if sub else None
    return (plan.limits if plan else {}), (plan.name if plan else "Trial")


@router.get("/departments")
def list_departments(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Department).filter_by(tenant_id=p.tenant_id).all()
    return [{"id": d.id, "name": d.name, "parent_id": d.parent_id,
             "isolation": d.isolation} for d in rows]


class DeptIn(BaseModel):
    name: str
    parent_id: str | None = None


@router.post("/departments")
def create_department(body: DeptIn, p: Principal = Depends(current_user),
                      db: Session = Depends(get_db)):
    d = Department(id=ulid("dep"), tenant_id=p.tenant_id, name=body.name,
                   parent_id=body.parent_id)
    db.add(d)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="department.create",
          target=d.id, tenant_id=p.tenant_id, meta={"name": body.name})
    db.commit()
    return {"id": d.id, "name": d.name}


@router.get("/agents")
def list_agents(department_id: str | None = None, status: str | None = None,
                p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(Agent).filter_by(tenant_id=p.tenant_id)
    if department_id:
        q = q.filter_by(department_id=department_id)
    if status:
        q = q.filter_by(status=status)
    return [agent_dto(a) for a in q.order_by(Agent.is_ceo.desc(), Agent.created_at).all()]


@router.get("/agents/{agent_id}")
def get_agent(agent_id: str, p: Principal = Depends(current_user),
              db: Session = Depends(get_db)):
    a = db.get(Agent, agent_id)
    if not a or a.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Agent not found"})
    return agent_dto(a)


class AgentIn(BaseModel):
    name: str
    designation: str
    department_id: str | None = None
    description: str | None = None
    objectives: list[str] = []
    model_id: str | None = "mdl_qwen14b_q4"
    model_tier: str = "local"
    skills: list[str] = []
    tools: list[str] = []
    permissions: dict = {}
    reporting_manager_id: str | None = None
    voice_id: str | None = "piper-female-1"


@router.post("/agents")
def create_agent(body: AgentIn, p: Principal = Depends(current_user),
                 db: Session = Depends(get_db)):
    # SB-02 / plan-limit enforcement: block above plan agent cap.
    limits, plan_name = _plan_limits(db, p.tenant_id)
    cap = limits.get("agents")
    count = db.query(Agent).filter_by(tenant_id=p.tenant_id).filter(
        Agent.status != "archived").count()
    if cap is not None and cap != "unlimited" and isinstance(cap, int) and count >= cap:
        raise HTTPException(402, detail={
            "code": "PLAN_LIMIT_EXCEEDED",
            "message": f"Your {plan_name} plan allows {cap} agents. Upgrade or archive an agent.",
            "limit": cap, "current": count, "upgrade_url": "/billing",
        })
    a = Agent(id=ulid("agt"), tenant_id=p.tenant_id, name=body.name,
              designation=body.designation, department_id=body.department_id,
              description=body.description, objectives=body.objectives,
              model_id=body.model_id, model_tier=body.model_tier,
              skills=body.skills, tools=body.tools,
              permissions=body.permissions or {"spend_limit": 5000,
                                               "external_send": "approval_required"},
              reporting_manager_id=body.reporting_manager_id, voice_id=body.voice_id,
              status="idle")
    db.add(a)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="agent.hire",
          target=a.id, tenant_id=p.tenant_id, meta={"designation": body.designation})
    db.commit()
    hub.emit(p.tenant_id, "agent.status", {"agent_id": a.id, "status": "idle",
                                           "name": a.name, "event": "hired"})
    return agent_dto(a)


class AgentPatch(BaseModel):
    name: str | None = None
    designation: str | None = None
    department_id: str | None = None
    description: str | None = None
    objectives: list[str] | None = None
    model_id: str | None = None
    model_tier: str | None = None
    skills: list[str] | None = None
    tools: list[str] | None = None
    permissions: dict | None = None
    reporting_manager_id: str | None = None
    voice_id: str | None = None
    status: str | None = None


@router.patch("/agents/{agent_id}")
def update_agent(agent_id: str, body: AgentPatch, p: Principal = Depends(current_user),
                 db: Session = Depends(get_db)):
    a = db.get(Agent, agent_id)
    if not a or a.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Agent not found"})
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(a, field, val)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="agent.update",
          target=a.id, tenant_id=p.tenant_id)
    db.commit()
    hub.emit(p.tenant_id, "agent.status", {"agent_id": a.id, "status": a.status,
                                           "name": a.name})
    return agent_dto(a)


@router.post("/agents/{agent_id}/pause")
def pause_agent(agent_id: str, p: Principal = Depends(current_user),
                db: Session = Depends(get_db)):
    return _set_status(db, p, agent_id, "paused")


@router.post("/agents/{agent_id}/resume")
def resume_agent(agent_id: str, p: Principal = Depends(current_user),
                 db: Session = Depends(get_db)):
    return _set_status(db, p, agent_id, "idle")


@router.delete("/agents/{agent_id}")
def archive_agent(agent_id: str, p: Principal = Depends(current_user),
                  db: Session = Depends(get_db)):
    # SB-03: downgrade/delete archives (read-only), never hard-deletes.
    return _set_status(db, p, agent_id, "archived", action="agent.archive")


def _set_status(db, p, agent_id, status, action="agent.status"):
    a = db.get(Agent, agent_id)
    if not a or a.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Agent not found"})
    a.status = status
    audit(db, plane="local", actor=f"user:{p.user_id}", action=action,
          target=a.id, tenant_id=p.tenant_id, meta={"status": status})
    db.commit()
    hub.emit(p.tenant_id, "agent.status", {"agent_id": a.id, "status": status,
                                           "name": a.name})
    return agent_dto(a)


@router.get("/agents/{agent_id}/performance")
def agent_performance(agent_id: str, p: Principal = Depends(current_user),
                      db: Session = Depends(get_db)):
    a = db.get(Agent, agent_id)
    if not a or a.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Agent not found"})
    rows = db.query(AgentPerformance).filter_by(agent_id=agent_id).all()
    return [{"period": r.period, "tasks_completed": r.tasks_completed,
             "success_rate": r.success_rate, "error_rate": r.error_rate,
             "productivity_score": r.productivity_score,
             "utilization": r.utilization} for r in rows]


@router.get("/agents/{agent_id}/activity")
def agent_activity(agent_id: str, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    """G6 Glass-Box: a live/recent activity stream for an agent — what it's doing,
    bus messages it sent, tasks it touched, and audited actions."""
    a = db.get(Agent, agent_id)
    if not a or a.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Agent not found"})
    stream = []
    for m in (db.query(BusMessage).filter_by(from_agent_id=agent_id)
              .order_by(BusMessage.at.desc()).limit(20).all()):
        stream.append({"kind": "tool" if m.kind in ("result", "handoff") else "message",
                       "label": m.kind, "text": (m.content or {}).get("text", ""),
                       "at": m.at.isoformat() if m.at else None})
    for t in (db.query(Task).filter_by(assignee_agent_id=agent_id)
              .order_by(Task.updated_at.desc()).limit(8).all()):
        stream.append({"kind": "task", "label": t.status, "text": t.title,
                       "at": t.updated_at.isoformat() if t.updated_at else None})
    for au in (db.query(AuditLog).filter_by(target=agent_id).order_by(AuditLog.at.desc()).limit(8).all()):
        stream.append({"kind": "audit", "label": au.action, "text": au.action,
                       "at": au.at.isoformat() if au.at else None})
    stream.sort(key=lambda x: x["at"] or "", reverse=True)
    return {"agent": {"id": a.id, "name": a.name, "status": a.status}, "stream": stream[:30]}


# ──────────────────────── voice / natural-language control ───────────────────
_NAME_POOL = ["Maya", "Arjun", "Geeta", "Sam", "Neha", "Vikram", "Priya", "Karan",
              "Riya", "Dev", "Anita", "Rohan", "Kavya", "Aditya", "Sara", "Veer"]
_ROLE_WORDS = ("manager", "specialist", "designer", "developer", "assistant", "coordinator",
               "rep", "representative", "executive", "analyst", "writer", "marketer",
               "accountant", "officer", "agent", "engineer", "consultant", "strategist",
               "lead", "associate", "scientist", "recruiter", "planner", "advisor")


class ResolveIn(BaseModel):
    transcript: str


def _match_agent(db, tenant_id, text):
    low = text.lower()
    best, score = None, 0
    for a in (db.query(Agent).filter_by(tenant_id=tenant_id)
              .filter(Agent.status != "archived").all()):
        for w in re.findall(r"[a-z]+", (a.name or "").lower()):
            if len(w) > 2 and w in low and len(w) > score:
                best, score = a, len(w)
        # also match a distinctive designation word ("collections agent" -> Collections Agent)
        for w in re.findall(r"[a-z]+", (a.designation or "").lower()):
            if len(w) > 3 and w in low and len(w) > score and w not in ("agent",):
                best, score = a, len(w)
    return best


def _pick_name(db, tenant_id):
    used = {(a.name or "").lower() for a in db.query(Agent).filter_by(tenant_id=tenant_id).all()}
    for n in _NAME_POOL:
        if n.lower() not in used:
            return n
    return "Alex"


@router.post("/org/resolve")
def org_resolve(body: ResolveIn, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Turn a spoken/typed phrase into a concrete Org Chart action."""
    text = (body.transcript or "").strip()
    low = text.lower()
    if not text:
        return {"action": "none", "message": "I didn't catch that."}

    # add a department
    m = re.search(r"\b(?:add|create|new)\b.*\bdepartment\b\s*(?:called|named|:)?\s*(.+)$", text, re.I)
    if m and m.group(1).strip():
        name = re.sub(r"^(called|named|the|a|an)\s+", "", m.group(1).strip(), flags=re.I).strip(" '\".")
        if name:
            return {"action": "add_department", "name": name, "message": f"Adding department “{name}”."}

    # hire
    if re.search(r"\b(hire|recruit|onboard)\b", low) or \
       (re.search(r"\b(add|create)\b", low) and re.search(r"\b(employee|agent|" + "|".join(_ROLE_WORDS) + r")\b", low)):
        name = None
        mn = re.search(r"\b(?:called|named)\s+([A-Za-z][a-z]+)", text)
        if mn:
            name = mn.group(1).capitalize()
        desig = None
        md = re.search(r"\bas\s+(?:an|a)\s+([a-z][a-z /]+?)(?:\s+(?:in|for|reporting|to|called|named)\b|[.,]|$)", text, re.I) \
            or re.search(r"\b(?:hire|recruit|onboard|add|create)\s+(?:an|a|new|the)?\s+([a-z][a-z /]+?)(?:\s+(?:called|named|in|for|to)\b|[.,]|$)", text, re.I)
        if md:
            desig = re.sub(r"^(new|a|an|the|junior|senior)\s+", "", md.group(1).strip(), flags=re.I).strip()
            desig = re.sub(r"\b(employee|agent)\b\s*$", "", desig).strip() or desig
        # department mention
        dept = None
        for d in db.query(Department).filter_by(tenant_id=p.tenant_id).all():
            if d.name and d.name.lower() in low:
                dept = d.name
                break
        if not desig or desig in ("employee", "agent"):
            return {"action": "hire_open", "name": name, "department": dept,
                    "message": "Opening the hire form — tell me the role."}
        return {"action": "hire", "name": name, "designation": desig.title(), "department": dept,
                "message": f"Hiring a {desig.title()}{f' called {name}' if name else ''}."}

    # actions on a named agent
    a = _match_agent(db, p.tenant_id, text)
    if a:
        if re.search(r"\b(pause|stop|hold|suspend|freeze)\b", low):
            return {"action": "pause", "id": a.id, "name": a.name, "message": f"Pausing {a.name}."}
        if re.search(r"\b(resume|unpause|wake|reactivate|activate|un-?hold)\b", low):
            return {"action": "resume", "id": a.id, "name": a.name, "message": f"Resuming {a.name}."}
        if re.search(r"\b(fire|archive|remove|delete|let go|terminate|dismiss)\b", low):
            return {"action": "archive", "id": a.id, "name": a.name, "message": f"Archiving {a.name}."}
        if re.search(r"\b(show|open|view|see|details?|tell me about|profile)\b", low):
            return {"action": "open", "id": a.id, "name": a.name, "message": f"Opening {a.name}."}

    return {"action": "none",
            "message": "Try \"hire a social media manager\", \"pause Maya\", \"fire the collections agent\", "
                       "or \"add a department called Marketing\"."}
