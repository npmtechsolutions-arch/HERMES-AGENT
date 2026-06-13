"""Tasks: CEO-Agent planning, execution simulation, messaging bus."""
import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..ceo_agent import plan_task
from ..database import get_db
from ..deps import Principal, audit, current_user
from ..events import hub
from ..models import (Agent, Approval, BusMessage, BusThread, Task, now)
from ..security import ulid

router = APIRouter(tags=["tasks"])


def task_dto(t: Task):
    return {
        "id": t.id, "title": t.title, "description": t.description,
        "source": t.source, "assignee_agent_id": t.assignee_agent_id,
        "priority": t.priority, "status": t.status,
        "deadline": t.deadline.isoformat() if t.deadline else None,
        "plan": t.plan, "result": t.result, "utterance": t.utterance,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


@router.get("/tasks")
def list_tasks(status: str | None = None, agent_id: str | None = None,
               p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(Task).filter_by(tenant_id=p.tenant_id)
    if status:
        q = q.filter_by(status=status)
    if agent_id:
        q = q.filter_by(assignee_agent_id=agent_id)
    return [task_dto(t) for t in q.order_by(Task.created_at.desc()).all()]


@router.get("/tasks/{task_id}")
def get_task(task_id: str, p: Principal = Depends(current_user),
             db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t or t.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Task not found"})
    thread = db.query(BusThread).filter_by(task_id=task_id).first()
    msgs = []
    if thread:
        msgs = db.query(BusMessage).filter_by(thread_id=thread.id).order_by(
            BusMessage.at).all()
    approvals = db.query(Approval).filter_by(task_id=task_id).all()
    return {**task_dto(t),
            "bus": [{"from_agent_id": m.from_agent_id, "kind": m.kind,
                     "content": m.content, "at": m.at.isoformat()} for m in msgs],
            "approvals": [{"id": a.id, "state": a.state, "tier": a.current_tier,
                           "summary": a.action_summary, "rule_id": a.rule_id}
                          for a in approvals]}


class PlanIn(BaseModel):
    utterance: str | None = None
    description: str | None = None
    use_llm: bool = True


@router.post("/tasks/plan")
def plan(body: PlanIn, p: Principal = Depends(current_user),
         db: Session = Depends(get_db)):
    """CEO Agent decomposition — produces a plan, does NOT execute (UC-04)."""
    text = body.utterance or body.description or ""
    agents = db.query(Agent).filter_by(tenant_id=p.tenant_id).filter(
        Agent.status.notin_(["archived", "paused"])).all()
    result = plan_task(text, agents, use_llm=body.use_llm)
    return result


class TaskIn(BaseModel):
    title: str
    description: str | None = None
    utterance: str | None = None
    source: str = "manual"
    priority: str = "normal"
    assignee_agent_id: str | None = None
    deadline_hours: int | None = None
    plan: dict | None = None


@router.post("/tasks")
def create_task(body: TaskIn, p: Principal = Depends(current_user),
                db: Session = Depends(get_db)):
    deadline = now() + timedelta(hours=body.deadline_hours) if body.deadline_hours else None
    t = Task(id=ulid("tsk"), tenant_id=p.tenant_id, title=body.title,
             description=body.description, utterance=body.utterance,
             source=body.source, priority=body.priority,
             assignee_agent_id=body.assignee_agent_id, deadline=deadline,
             plan=body.plan, status="queued")
    db.add(t)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="task.create",
          target=t.id, tenant_id=p.tenant_id, meta={"title": body.title})
    db.commit()
    hub.emit(p.tenant_id, "task.status_changed",
             {"task_id": t.id, "old": None, "new": "queued", "title": t.title})
    return {**task_dto(t), "message": f"Task created: {t.title}"}


class TaskPatch(BaseModel):
    title: str | None = None
    priority: str | None = None
    assignee_agent_id: str | None = None
    deadline_hours: int | None = None
    status: str | None = None


@router.patch("/tasks/{task_id}")
def update_task(task_id: str, body: TaskPatch, p: Principal = Depends(current_user),
                db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t or t.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Task not found"})
    if body.title is not None:
        t.title = body.title
    if body.priority is not None:
        t.priority = body.priority
    if body.assignee_agent_id is not None:
        t.assignee_agent_id = body.assignee_agent_id or None
    if body.deadline_hours is not None:
        t.deadline = now() + timedelta(hours=body.deadline_hours)
    old = t.status
    if body.status is not None:
        t.status = body.status
    audit(db, plane="local", actor=f"user:{p.user_id}", action="task.update",
          target=t.id, tenant_id=p.tenant_id)
    db.commit()
    if body.status is not None and body.status != old:
        hub.emit(p.tenant_id, "task.status_changed",
                 {"task_id": t.id, "old": old, "new": t.status, "title": t.title})
    return {**task_dto(t), "message": f"Task “{t.title}” updated."}


class QuickIn(BaseModel):
    utterance: str
    execute: bool = False
    use_llm: bool = False


@router.post("/tasks/quick")
def quick_task(body: QuickIn, p: Principal = Depends(current_user),
               db: Session = Depends(get_db)):
    """Voice-friendly: plan + create a task in one call (optionally execute)."""
    agents = db.query(Agent).filter_by(tenant_id=p.tenant_id).filter(
        Agent.status.notin_(["archived", "paused"])).all()
    plan = plan_task(body.utterance, agents, use_llm=body.use_llm)
    t = Task(id=ulid("tsk"), tenant_id=p.tenant_id, title=body.utterance[:80],
             utterance=body.utterance, source="voice",
             priority="urgent" if plan.get("amount_detected") else "normal",
             plan=plan, status="queued")
    db.add(t)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="task.create",
          target=t.id, tenant_id=p.tenant_id, meta={"title": t.title, "via": "voice"})
    db.commit()
    hub.emit(p.tenant_id, "task.status_changed",
             {"task_id": t.id, "old": None, "new": "queued", "title": t.title})
    if body.execute:
        execute_task(t.id, p, db)
        db.refresh(t)
    return {**task_dto(t), "message": f"Task created: {t.title}"
            + (" — executing." if body.execute else ".")}


@router.post("/tasks/{task_id}/execute")
def execute_task(task_id: str, p: Principal = Depends(current_user),
                 db: Session = Depends(get_db)):
    """
    Simulate execution: spin up a bus thread, post agent messages, possibly open
    an approval gate, and advance task state. (Local-only; zero cloud.)
    """
    t = db.get(Task, task_id)
    if not t or t.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Task not found"})

    plan = t.plan or {}
    subtasks = plan.get("subtasks", [])
    # Create / reuse bus thread (FR-O6, UC-11).
    thread = db.query(BusThread).filter_by(task_id=task_id).first()
    if not thread:
        participants = [s["agent_id"] for s in subtasks if s.get("agent_id")]
        thread = BusThread(id=ulid("bth"), tenant_id=p.tenant_id, task_id=task_id,
                           topic=t.title, participants=participants)
        db.add(thread)
        db.flush()

    t.status = "working"
    hub.emit(p.tenant_id, "task.status_changed",
             {"task_id": t.id, "old": "queued", "new": "working", "title": t.title})

    for s in subtasks:
        if not s.get("agent_id"):
            continue
        ag = db.get(Agent, s["agent_id"])
        if ag:
            ag.status = "working"
            hub.emit(p.tenant_id, "agent.status",
                     {"agent_id": ag.id, "status": "working", "name": ag.name})
        db.add(BusMessage(id=ulid("bmsg"), thread_id=thread.id,
                          from_agent_id=s["agent_id"], kind="status",
                          content={"text": f"Starting: {s['description']}"}))

    # Approval gate (UC-10 / Flow 3): if plan requires approval, open one + pause.
    appr = (plan.get("approval") or {})
    if plan.get("requires_approval"):
        a = Approval(
            id=ulid("apv"), tenant_id=p.tenant_id,
            requester_agent_id=(subtasks[0]["agent_id"] if subtasks else None),
            task_id=task_id, action_summary=t.title,
            payload={"amount": plan.get("amount_detected")},
            rule_id=appr.get("rule", "AC-04"), current_tier=appr.get("tier", "human"),
            state="pending", chain=[], expires_at=now() + timedelta(hours=4))
        db.add(a)
        t.status = "waiting"
        hub.emit(p.tenant_id, "task.status_changed",
                 {"task_id": t.id, "old": "working", "new": "waiting", "title": t.title})
        hub.emit(p.tenant_id, "approval.requested",
                 {"approval_id": a.id, "summary": t.title, "tier": a.current_tier,
                  "rule_id": a.rule_id, "reason": appr.get("reason")})
        audit(db, plane="local", actor="agent:ceo", action="approval.request",
              target=a.id, tenant_id=p.tenant_id, meta={"rule": a.rule_id})
        db.commit()
        return {**task_dto(t), "approval_required": True, "approval_id": a.id}

    # No approval: complete it, write operational memory result.
    _complete_task(db, p, t, thread)
    db.commit()
    return {**task_dto(t), "approval_required": False}


def _complete_task(db, p, t, thread):
    for s in (t.plan or {}).get("subtasks", []):
        if s.get("agent_id"):
            db.add(BusMessage(id=ulid("bmsg"), thread_id=thread.id,
                              from_agent_id=s["agent_id"], kind="result",
                              content={"text": f"Done: {s['description']}"}))
            ag = db.get(Agent, s["agent_id"])
            if ag:
                ag.status = "idle"
                hub.emit(p.tenant_id, "agent.status",
                         {"agent_id": ag.id, "status": "idle", "name": ag.name})
    t.status = "completed"
    subtasks = (t.plan or {}).get("subtasks", [])
    t.result = {"summary": f"Completed '{t.title}' across {len(subtasks)} steps.",
                "completed_at": now().isoformat()}
    audit(db, plane="local", actor="agent:ceo", action="task.complete",
          target=t.id, tenant_id=p.tenant_id)
    # G3 Auto-Skill Capture: draft a reusable skill from this multi-step success.
    from .skills import capture_skill
    capture_skill(db, p.tenant_id, t.title, subtasks, t.id, agent_name="the CEO Agent")
    hub.emit(p.tenant_id, "task.status_changed",
             {"task_id": t.id, "old": "working", "new": "completed", "title": t.title})


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str, p: Principal = Depends(current_user),
                db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t or t.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Task not found"})
    old = t.status
    t.status = "canceled"   # TC-11 graceful stop
    audit(db, plane="local", actor=f"user:{p.user_id}", action="task.cancel",
          target=t.id, tenant_id=p.tenant_id)
    db.commit()
    hub.emit(p.tenant_id, "task.status_changed",
             {"task_id": t.id, "old": old, "new": "canceled", "title": t.title})
    return {**task_dto(t), "message": f"Task “{t.title}” canceled."}


@router.get("/bus/threads")
def bus_threads(task_id: str | None = None, p: Principal = Depends(current_user),
                db: Session = Depends(get_db)):
    q = db.query(BusThread).filter_by(tenant_id=p.tenant_id)
    if task_id:
        q = q.filter_by(task_id=task_id)
    out = []
    for th in q.order_by(BusThread.created_at.desc()).all():
        msgs = db.query(BusMessage).filter_by(thread_id=th.id).order_by(BusMessage.at).all()
        out.append({"id": th.id, "topic": th.topic, "task_id": th.task_id,
                    "participants": th.participants,
                    "messages": [{"from_agent_id": m.from_agent_id, "kind": m.kind,
                                  "content": m.content, "at": m.at.isoformat()}
                                 for m in msgs]})
    return out


# ──────────────────────── voice / natural-language control ───────────────────
class TaskVoiceIn(BaseModel):
    transcript: str


_CREATE_RE = re.compile(
    r"\b(?:create|add|new|make|set ?up|open)\s+(?:a\s+|an\s+|the\s+)?task\s+(?:to\s+|for\s+|that\s+|about\s+|:|called\s+|named\s+)?(.+)$", re.I)
_TODO_RE = re.compile(r"\b(?:remind me to|i need to|i want to|todo|to-?do|task to)\s+(.+)$", re.I)


def _match_task(db, tenant_id, text):
    low = text.lower()
    best, score = None, 0
    for t in (db.query(Task).filter_by(tenant_id=tenant_id)
              .filter(Task.status.notin_(["completed", "canceled"]))
              .order_by(Task.created_at.desc()).all()):
        title = (t.title or "").lower()
        if title and title in low:
            return t
        _stop = {"task", "the", "and", "for", "with", "your", "you", "from", "into", "this", "that"}
        for w in re.findall(r"[a-z]+", title):
            if len(w) > 2 and w not in _stop and w in low and len(w) > score:
                best, score = t, len(w)
    return best


@router.post("/tasks/resolve")
def tasks_resolve(body: TaskVoiceIn, p: Principal = Depends(current_user),
                  db: Session = Depends(get_db)):
    """Turn a spoken/typed phrase into a concrete Tasks action."""
    text = (body.transcript or "").strip()
    low = text.lower()
    if not text:
        return {"action": "none", "message": "I didn't catch that."}

    # act on an existing task first (execute / cancel / open)
    tk = _match_task(db, p.tenant_id, text)
    if tk and re.search(r"\b(execute|run|start|do it|proceed|kick off|go ahead)\b", low):
        return {"action": "execute_task", "id": tk.id, "title": tk.title,
                "message": f"Executing “{tk.title}”."}
    if tk and re.search(r"\b(cancel|stop|abort|kill|halt|drop)\b", low):
        return {"action": "cancel_task", "id": tk.id, "title": tk.title,
                "message": f"Canceling “{tk.title}”."}
    if tk and re.search(r"\b(show|open|view|see|details?|pull up)\b", low):
        return {"action": "open_task", "id": tk.id, "title": tk.title,
                "message": f"Opening “{tk.title}”."}

    # create a task
    m = _CREATE_RE.search(text) or _TODO_RE.search(text)
    if m and m.group(1).strip():
        return {"action": "create_task", "utterance": m.group(1).strip(" .'\""),
                "execute": bool(re.search(r"\b(and (execute|run|do it)|then (execute|run)|right (away|now))\b", low)),
                "message": "Creating the task."}
    if re.search(r"\b(create|add|new)\b", low) and "task" in low:
        return {"action": "plan_open", "message": "Opening the planner — what's the task?"}

    return {"action": "none",
            "message": "Try \"create a task to prepare the GST report\", \"run the report task\", "
                       "or \"cancel the GST task\"."}
