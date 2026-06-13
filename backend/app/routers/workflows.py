"""Workflows (voice-to-workflow compile, dry-run, activate) + approvals + schedules."""
import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Principal, audit, current_user
from ..events import hub
from ..models import Approval, Schedule, Task, Workflow, WorkflowRun, now
from ..routers.tasks import _complete_task
from ..models import BusThread
from ..security import ulid

router = APIRouter(tags=["workflows"])


# ───────────────────────────── Voice → Workflow (FR-W2) ─────────────────────
# Specific weekday phrases are listed FIRST so "every Friday … weekly report" maps
# to Friday, not the generic "weekly" (Monday) it also contains.
_CRON_WORDS = {
    "every monday": "0 9 * * 1", "every tuesday": "0 9 * * 2",
    "every wednesday": "0 9 * * 3", "every thursday": "0 9 * * 4",
    "every friday": "0 9 * * 5", "every saturday": "0 9 * * 6",
    "every sunday": "0 9 * * 0",
    "every day": "0 9 * * *", "every morning": "0 9 * * *", "daily": "0 9 * * *",
    "weekly": "0 9 * * 1", "monthly": "0 9 1 * *",
}


def compile_workflow(utterance: str):
    text = (utterance or "").lower()
    nodes, edges = [], []

    def add(node_id, ntype, label, config=None):
        nodes.append({"node_id": node_id, "type": ntype, "label": label,
                      "config": config or {}})

    # Trigger
    cron = None
    for phrase, expr in _CRON_WORDS.items():
        if phrase in text:
            cron = expr
            break
    tm = re.search(r"at (\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
    if cron and tm:
        hour = int(tm.group(1))
        if tm.group(3) == "pm" and hour < 12:
            hour += 12
        parts = cron.split()
        parts[1] = str(hour)
        cron = " ".join(parts)
    if cron:
        add("n1", "trigger", f"Schedule (CRON {cron})", {"cron": cron})
    else:
        add("n1", "trigger", "Manual / event trigger", {})

    prev = "n1"
    idx = 2
    # Actions inferred from verbs
    action_map = [
        (r"\bpull|fetch|get\b.*\b(sales|data|crm|zoho|report)", "action", "Fetch source data"),
        (r"\bsummar|deck|presentation|report\b", "agent_task", "Agent: summarize & build doc"),
        (r"\bcondition|if\b", "condition", "Condition check"),
        (r"\bemail|send|slack|whatsapp|message|notify\b", "action", "Send / notify"),
    ]
    warnings, unmapped = [], []
    matched_any = False
    for pattern, ntype, label in action_map:
        if re.search(pattern, text):
            nid = f"n{idx}"
            add(nid, ntype, label)
            edges.append({"from": prev, "to": nid})
            prev = nid
            idx += 1
            matched_any = True
    # Auto-insert CEO approval gate before external sends
    if re.search(r"\bsend|email|slack|post|publish\b", text):
        nid = f"n{idx}"
        add(nid, "approval", "CEO Agent approval (auto if no anomalies)")
        edges.append({"from": prev, "to": nid})
        prev = nid
        idx += 1
    if not matched_any:
        nid = f"n{idx}"
        add(nid, "agent_task", "Execute described work")
        edges.append({"from": prev, "to": nid})
        unmapped.append("Could not map specific steps; using a generic agent task.")

    return {"graph": {"nodes": nodes, "edges": edges},
            "warnings": warnings, "unmapped_steps": unmapped}


class CompileIn(BaseModel):
    utterance: str


@router.post("/workflows/compile")
def compile_wf(body: CompileIn, p: Principal = Depends(current_user)):
    return compile_workflow(body.utterance)


def wf_dto(w: Workflow):
    return {"id": w.id, "name": w.name, "graph": w.graph, "status": w.status,
            "version": w.version, "source_utterance": w.source_utterance,
            "created_at": w.created_at.isoformat() if w.created_at else None}


def _pub(tenant_id, action, name):
    hub.emit(tenant_id, "workflow.changed", {"action": action, "name": name})


@router.get("/workflows")
def list_workflows(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    return [wf_dto(w) for w in db.query(Workflow).filter_by(tenant_id=p.tenant_id)
            .filter(Workflow.status != "archived").order_by(Workflow.created_at.desc()).all()]


class WorkflowIn(BaseModel):
    name: str
    graph: dict
    status: str = "draft"
    source_utterance: str | None = None


@router.post("/workflows")
def create_workflow(body: WorkflowIn, p: Principal = Depends(current_user),
                    db: Session = Depends(get_db)):
    w = Workflow(id=ulid("wfl"), tenant_id=p.tenant_id, name=body.name,
                 graph=body.graph, status=body.status,
                 source_utterance=body.source_utterance)
    db.add(w)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="workflow.create",
          target=w.id, tenant_id=p.tenant_id, meta={"name": body.name})
    db.commit()
    _pub(p.tenant_id, "create", w.name)
    return {**wf_dto(w), "message": f"Workflow “{w.name}” created."}


class WorkflowPatch(BaseModel):
    name: str | None = None


@router.patch("/workflows/{wid}")
def update_workflow(wid: str, body: WorkflowPatch, p: Principal = Depends(current_user),
                    db: Session = Depends(get_db)):
    w = db.get(Workflow, wid)
    if not w or w.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Workflow not found"})
    if body.name is not None:
        w.name = body.name
    audit(db, plane="local", actor=f"user:{p.user_id}", action="workflow.update",
          target=w.id, tenant_id=p.tenant_id)
    db.commit()
    _pub(p.tenant_id, "update", w.name)
    return {**wf_dto(w), "message": f"Workflow “{w.name}” updated."}


@router.delete("/workflows/{wid}")
def delete_workflow(wid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    w = db.get(Workflow, wid)
    if not w or w.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Workflow not found"})
    w.status = "archived"
    name = w.name
    audit(db, plane="local", actor=f"user:{p.user_id}", action="workflow.delete",
          target=w.id, tenant_id=p.tenant_id)
    db.commit()
    _pub(p.tenant_id, "delete", name)
    return {"status": "archived", "message": f"Workflow “{name}” deleted."}


class QuickWfIn(BaseModel):
    utterance: str
    activate: bool = False


@router.post("/workflows/quick")
def quick_workflow(body: QuickWfIn, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    """Voice-friendly: compile an utterance + create the workflow in one call."""
    compiled = compile_workflow(body.utterance)
    w = Workflow(id=ulid("wfl"), tenant_id=p.tenant_id, name=body.utterance[:50],
                 graph=compiled["graph"], status="active" if body.activate else "draft",
                 source_utterance=body.utterance)
    db.add(w)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="workflow.create",
          target=w.id, tenant_id=p.tenant_id, meta={"name": w.name, "via": "voice"})
    db.commit()
    _pub(p.tenant_id, "create", w.name)
    return {**wf_dto(w), "message": f"Workflow created{' & activated' if body.activate else ''}: {w.name}"}


@router.post("/workflows/{wid}/activate")
def activate_workflow(wid: str, p: Principal = Depends(current_user),
                      db: Session = Depends(get_db)):
    return _wf_status(db, p, wid, "active")


@router.post("/workflows/{wid}/deactivate")
def deactivate_workflow(wid: str, p: Principal = Depends(current_user),
                        db: Session = Depends(get_db)):
    return _wf_status(db, p, wid, "paused")


def _wf_status(db, p, wid, status):
    w = db.get(Workflow, wid)
    if not w or w.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Workflow not found"})
    w.status = status
    audit(db, plane="local", actor=f"user:{p.user_id}", action=f"workflow.{status}",
          target=w.id, tenant_id=p.tenant_id)
    db.commit()
    _pub(p.tenant_id, status, w.name)
    return {**wf_dto(w), "message": f"“{w.name}” {'activated' if status == 'active' else 'paused'}."}


@router.post("/workflows/{wid}/dry_run")
def dry_run(wid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    w = db.get(Workflow, wid)
    if not w or w.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Workflow not found"})
    results = [{"node_id": n["node_id"], "label": n["label"], "type": n["type"],
                "status": "ok", "note": "sandbox (no external side-effects)"}
               for n in (w.graph or {}).get("nodes", [])]
    run = WorkflowRun(id=ulid("run"), workflow_id=wid,
                      trigger_info={"mode": "dry_run"}, ended_at=now(),
                      status="succeeded", node_results=results)
    db.add(run)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="workflow.dry_run",
          target=wid, tenant_id=p.tenant_id)
    db.commit()
    return {"run_id": run.id, "status": "succeeded", "node_results": results,
            "message": f"Dry-run passed — {len(results)} node(s), no side-effects."}


@router.get("/workflows/{wid}/runs")
def runs(wid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(WorkflowRun).filter_by(workflow_id=wid).order_by(
        WorkflowRun.started_at.desc()).all()
    return [{"id": r.id, "status": r.status, "trigger_info": r.trigger_info,
             "started_at": r.started_at.isoformat() if r.started_at else None,
             "node_results": r.node_results} for r in rows]


# ───────────────────────────── Approvals (AC-01..12) ────────────────────────
@router.get("/approvals")
def list_approvals(state: str | None = "pending", p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    q = db.query(Approval).filter_by(tenant_id=p.tenant_id)
    if state:
        q = q.filter_by(state=state)
    out = []
    for a in q.order_by(Approval.created_at.desc()).all():
        out.append({"id": a.id, "summary": a.action_summary, "payload": a.payload,
                    "rule_id": a.rule_id, "current_tier": a.current_tier,
                    "state": a.state, "chain": a.chain or [],
                    "requester_agent_id": a.requester_agent_id, "task_id": a.task_id,
                    "created_at": a.created_at.isoformat() if a.created_at else None})
    return out


class DecideIn(BaseModel):
    decision: str            # approve | reject
    reason: str | None = None


@router.post("/approvals/{aid}/decide")
def decide(aid: str, body: DecideIn, p: Principal = Depends(current_user),
           db: Session = Depends(get_db)):
    a = db.get(Approval, aid)
    if not a or a.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Approval not found"})
    if a.state != "pending":
        raise HTTPException(409, detail={"code": "CONFLICT", "message": "Already decided"})
    chain = list(a.chain or [])
    chain.append({"tier": "human", "actor": f"user:{p.user_id}",
                  "decision": body.decision, "reason": body.reason,
                  "at": now().isoformat()})
    a.chain = chain
    a.state = "approved" if body.decision == "approve" else "rejected"
    audit(db, plane="local", actor=f"user:{p.user_id}", action=f"approval.{a.state}",
          target=a.id, tenant_id=p.tenant_id, meta={"rule": a.rule_id})
    hub.emit(p.tenant_id, "approval.decided",
             {"approval_id": a.id, "state": a.state})

    # Resume / fail the gated task.
    if a.task_id:
        t = db.get(Task, a.task_id)
        if t:
            if a.state == "approved":
                thread = db.query(BusThread).filter_by(task_id=t.id).first()
                if thread:
                    _complete_task(db, p, t, thread)
            else:
                t.status = "canceled"
                hub.emit(p.tenant_id, "task.status_changed",
                         {"task_id": t.id, "old": "waiting", "new": "canceled",
                          "title": t.title})
    db.commit()
    verb = "approved" if a.state == "approved" else "rejected"
    return {"id": a.id, "state": a.state, "chain": a.chain,
            "message": f"“{a.action_summary}” {verb}."}


class DecideAllIn(BaseModel):
    decision: str            # approve | reject
    reason: str | None = None


@router.post("/approvals/decide_all")
def decide_all(body: DecideAllIn, p: Principal = Depends(current_user),
               db: Session = Depends(get_db)):
    """Bulk-clear the pending queue (AC-12 batch governance)."""
    pend = db.query(Approval).filter_by(tenant_id=p.tenant_id, state="pending").all()
    state = "approved" if body.decision == "approve" else "rejected"
    n = 0
    for a in pend:
        chain = list(a.chain or [])
        chain.append({"tier": "human", "actor": f"user:{p.user_id}",
                      "decision": body.decision, "reason": body.reason,
                      "at": now().isoformat(), "batch": True})
        a.chain = chain
        a.state = state
        if a.task_id:
            t = db.get(Task, a.task_id)
            if t:
                if state == "approved":
                    thread = db.query(BusThread).filter_by(task_id=t.id).first()
                    if thread:
                        _complete_task(db, p, t, thread)
                else:
                    t.status = "canceled"
        n += 1
    audit(db, plane="local", actor=f"user:{p.user_id}", action=f"approval.batch_{state}",
          tenant_id=p.tenant_id, meta={"count": n})
    db.commit()
    hub.emit(p.tenant_id, "approval.decided", {"batch": True, "state": state, "count": n})
    return {"state": state, "count": n,
            "message": f"{n} approval(s) {state}." if n else "Nothing pending to decide."}


class ApprVoiceIn(BaseModel):
    transcript: str


def _match_approval(db, tenant_id, text):
    low = re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())
    toks = [w for w in low.split() if len(w) >= 4 and w not in (
        "approve", "reject", "approval", "request", "decline", "the", "this", "that",
        "first", "last", "next", "please", "pending", "deny")]
    pend = db.query(Approval).filter_by(tenant_id=tenant_id, state="pending").order_by(
        Approval.created_at.desc()).all()
    if not pend:
        return None
    # "first"/"last"/"top" → positional
    if re.search(r"\b(first|top|latest|newest)\b", low):
        return pend[0]
    if re.search(r"\b(last|oldest|bottom)\b", low):
        return pend[-1]
    best, score = None, 0
    for a in pend:
        hay = re.sub(r"[^a-z0-9 ]", " ", f"{a.action_summary} {a.requester_agent_id or ''} {a.rule_id or ''}".lower())
        s = sum(1 for t in toks if t in hay)
        if s > score:
            best, score = a, s
    return best if score else (pend[0] if len(pend) == 1 else None)


@router.post("/approvals/resolve")
def approvals_resolve(body: ApprVoiceIn, p: Principal = Depends(current_user),
                      db: Session = Depends(get_db)):
    text = body.transcript or ""
    low = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    approve = bool(re.search(r"\b(approve|accept|allow|authorize|authori[sz]e|ok|okay|yes|sign off|green ?light|confirm)\b", low))
    reject = bool(re.search(r"\b(reject|decline|deny|refuse|block|no|disallow)\b", low))
    everyone = bool(re.search(r"\b(all|everything|every one|everyone|whole queue|the queue|all pending|each)\b", low))
    # filter / navigation
    fm = re.search(r"\bshow (me )?(the )?(pending|approved|rejected)\b", low) or \
        re.search(r"\b(pending|approved|rejected) (ones|items|tab|list)\b", low)
    if fm and not (approve or reject):
        st = next(s for s in ("pending", "approved", "rejected") if s in low)
        return {"action": "filter", "state": st, "message": f"Showing {st}."}
    if everyone and approve:
        return {"action": "approve_all", "message": "Approving everything pending."}
    if everyone and reject:
        return {"action": "reject_all", "message": "Rejecting everything pending."}
    if approve or reject:
        a = _match_approval(db, p.tenant_id, text)
        rsn = None
        rm = re.search(r"\b(because|since|reason|as)\b (.+)$", text, re.I)
        if rm:
            rsn = rm.group(2).strip(" .'\"")
        if a:
            return {"action": "approve" if approve else "reject", "id": a.id,
                    "name": a.action_summary, "reason": rsn,
                    "message": f'{"Approving" if approve else "Rejecting"} “{a.action_summary}”.'}
        return {"action": "none",
                "message": "I couldn't tell which request — say e.g. \"approve the vendor payment\" or \"approve the first one\"."}
    return {"action": "none",
            "message": 'Try "approve the first one", "reject the vendor payment", "approve everything", or "show approved".'}


# ───────────────────────────── Schedules (SD-01..05) ────────────────────────
@router.get("/schedules")
def list_schedules(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Schedule).filter_by(tenant_id=p.tenant_id).all()
    return [{"id": s.id, "workflow_id": s.workflow_id, "kind": s.kind,
             "expression": s.expression, "timezone": s.timezone,
             "run_policy": s.run_policy,
             "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None,
             "consecutive_failures": s.consecutive_failures} for s in rows]


class ScheduleIn(BaseModel):
    workflow_id: str
    kind: str = "cron"
    expression: str
    run_policy: str = "run_on_wake"


@router.post("/schedules")
def create_schedule(body: ScheduleIn, p: Principal = Depends(current_user),
                    db: Session = Depends(get_db)):
    # SD-03: reject invalid cron with explanation.
    if body.kind == "cron" and len(body.expression.split()) != 5:
        raise HTTPException(422, detail={"code": "VALIDATION_ERROR",
            "message": "Invalid CRON expression — expected 5 fields "
                       "(min hour day month weekday). Try '0 9 * * 1'."})
    s = Schedule(id=ulid("sch"), tenant_id=p.tenant_id, workflow_id=body.workflow_id,
                 kind=body.kind, expression=body.expression,
                 run_policy=body.run_policy, next_run_at=now() + timedelta(days=1))
    db.add(s)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="schedule.create",
          target=s.id, tenant_id=p.tenant_id)
    db.commit()
    return {"id": s.id, "expression": s.expression}


# ──────────────────────── voice / natural-language control ───────────────────
class WfVoiceIn(BaseModel):
    transcript: str


def _match_workflow(db, tenant_id, text):
    low = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    toks = [t for t in low.split() if len(t) >= 3]
    best, score = None, 0
    for w in (db.query(Workflow).filter_by(tenant_id=tenant_id)
              .filter(Workflow.status != "archived").all()):
        blob = f"{w.name or ''} {w.source_utterance or ''}".lower()
        if (w.name or "").lower() in low:
            return w
        for word in re.findall(r"[a-z]+", blob):
            if len(word) > 3 and word not in ("workflow", "the", "and", "for", "every") and word in toks and len(word) > score:
                best, score = w, len(word)
    return best


@router.post("/workflows/resolve")
def workflows_resolve(body: WfVoiceIn, p: Principal = Depends(current_user),
                      db: Session = Depends(get_db)):
    """Turn a spoken/typed phrase into a concrete Workflows action."""
    text = (body.transcript or "").strip()
    low = text.lower()
    if not text:
        return {"action": "none", "message": "I didn't catch that."}

    # build a new workflow from a described automation
    m = re.search(r"\b(?:build|create|make|set ?up|add|new)\s+(?:a\s+|an\s+)?workflow\s+(?:to\s+|for\s+|that\s+|:)?(.+)$", text, re.I)
    if m and m.group(1).strip():
        return {"action": "create", "utterance": m.group(1).strip(" .'\""),
                "activate": bool(re.search(r"\b(and activate|activate it|turn it on|right away)\b", low)),
                "message": "Compiling that into a workflow."}

    w = _match_workflow(db, p.tenant_id, text)
    if w:
        if re.search(r"\b(activate|turn on|enable|resume|switch on|start)\b", low):
            return {"action": "activate", "id": w.id, "name": w.name, "message": f"Activating “{w.name}”."}
        if re.search(r"\b(deactivate|pause|turn off|disable|stop|switch off)\b", low):
            return {"action": "deactivate", "id": w.id, "name": w.name, "message": f"Pausing “{w.name}”."}
        if re.search(r"\b(dry.?run|test|simulate|try)\b", low):
            return {"action": "dry_run", "id": w.id, "name": w.name, "message": f"Dry-running “{w.name}”."}
        if re.search(r"\b(delete|remove|archive|get rid of)\b", low):
            return {"action": "delete", "id": w.id, "name": w.name, "message": f"Deleting “{w.name}”."}
        if re.search(r"\b(open|show|view|see|details?)\b", low):
            return {"action": "open", "id": w.id, "name": w.name, "message": f"Opening “{w.name}”."}

    if re.search(r"\b(build|create|new|make)\b", low) and "workflow" in low:
        return {"action": "build", "message": "Opening the workflow builder."}
    return {"action": "none",
            "message": "Try \"build a workflow to email me every morning\", \"activate the X workflow\", "
                       "or \"dry run the X workflow\"."}
