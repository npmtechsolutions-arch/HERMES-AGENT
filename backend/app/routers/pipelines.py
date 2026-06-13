"""
Agent Pipelines — the sequential "AI crew" run engine.

A pipeline chains agents (Agent 1 → 2 → … → N). Running it executes one step at
a time via the local LLM (with fallback): each agent produces real output, using
the previous agents' outputs as context. Steps flagged `requires_approval` pause
the run so the user can verify the output before the next agent starts. When all
steps finish, a final consolidated report is generated.

Stepwise advancement (POST /advance) keeps each slow LLM call to a single request
and integrates cleanly with the per-step approval gates.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import re

from .. import llm
from ..database import get_db
from ..deps import Principal, audit, current_user
from ..events import hub
from ..models import (Agent, Pipeline, PipelineRun, PipelineStep, PipelineStepRun,
                      Tenant, now)
from ..security import ulid

router = APIRouter(tags=["pipelines"])


# ───────────────────────────── Serialization ────────────────────────────────
def step_dto(s: PipelineStep, agents):
    ag = agents.get(s.agent_id)
    return {"id": s.id, "seq": s.seq, "agent_id": s.agent_id,
            "agent_name": ag.name if ag else "Unassigned",
            "agent_designation": ag.designation if ag else None,
            "instruction": s.instruction, "requires_approval": s.requires_approval}


def pipeline_dto(db, pl: Pipeline):
    steps = db.query(PipelineStep).filter_by(pipeline_id=pl.id).order_by(PipelineStep.seq).all()
    agents = {a.id: a for a in db.query(Agent).filter_by(tenant_id=pl.tenant_id).all()}
    last = db.query(PipelineRun).filter_by(pipeline_id=pl.id).order_by(
        PipelineRun.started_at.desc()).first()
    return {"id": pl.id, "name": pl.name, "description": pl.description,
            "status": pl.status, "source": pl.source, "product_id": pl.product_id,
            "steps": [step_dto(s, agents) for s in steps],
            "last_run": {"id": last.id, "status": last.status} if last else None}


# ───────────────────────────── CRUD ─────────────────────────────────────────
@router.get("/pipelines")
def list_pipelines(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Pipeline).filter_by(tenant_id=p.tenant_id).filter(
        Pipeline.status != "archived").order_by(Pipeline.created_at.desc()).all()
    return [pipeline_dto(db, pl) for pl in rows]


@router.get("/pipelines/{pid}")
def get_pipeline(pid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    pl = db.get(Pipeline, pid)
    if not pl or pl.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Pipeline not found"})
    return pipeline_dto(db, pl)


class StepIn(BaseModel):
    agent_id: str
    instruction: str
    requires_approval: bool = False


class PipelineIn(BaseModel):
    name: str
    description: str | None = None
    product_id: str | None = None
    steps: list[StepIn] = []


@router.post("/pipelines")
def create_pipeline(body: PipelineIn, p: Principal = Depends(current_user),
                    db: Session = Depends(get_db)):
    pl = Pipeline(id=ulid("ppl"), tenant_id=p.tenant_id, name=body.name,
                  description=body.description, product_id=body.product_id,
                  status="ready", source="custom")
    db.add(pl)
    db.flush()
    for i, st in enumerate(body.steps, start=1):
        db.add(PipelineStep(id=ulid("pst"), pipeline_id=pl.id, seq=i,
                            agent_id=st.agent_id, instruction=st.instruction,
                            requires_approval=st.requires_approval))
    audit(db, plane="local", actor=f"user:{p.user_id}", action="pipeline.create",
          target=pl.id, tenant_id=p.tenant_id, meta={"name": body.name})
    db.commit()
    hub.emit(p.tenant_id, "pipeline.changed", {"action": "create", "name": pl.name})
    return {**pipeline_dto(db, pl), "message": f"Pipeline “{pl.name}” created."}


@router.patch("/pipelines/{pid}")
def update_pipeline(pid: str, body: PipelineIn, p: Principal = Depends(current_user),
                    db: Session = Depends(get_db)):
    pl = db.get(Pipeline, pid)
    if not pl or pl.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Pipeline not found"})
    pl.name = body.name
    pl.description = body.description
    db.query(PipelineStep).filter_by(pipeline_id=pid).delete()
    db.flush()
    for i, st in enumerate(body.steps, start=1):
        db.add(PipelineStep(id=ulid("pst"), pipeline_id=pid, seq=i,
                            agent_id=st.agent_id, instruction=st.instruction,
                            requires_approval=st.requires_approval))
    audit(db, plane="local", actor=f"user:{p.user_id}", action="pipeline.update",
          target=pl.id, tenant_id=p.tenant_id)
    db.commit()
    hub.emit(p.tenant_id, "pipeline.changed", {"action": "update", "name": pl.name})
    return {**pipeline_dto(db, pl), "message": f"Pipeline “{pl.name}” updated."}


@router.delete("/pipelines/{pid}")
def delete_pipeline(pid: str, p: Principal = Depends(current_user),
                    db: Session = Depends(get_db)):
    pl = db.get(Pipeline, pid)
    if not pl or pl.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Pipeline not found"})
    pl.status = "archived"
    name = pl.name
    audit(db, plane="local", actor=f"user:{p.user_id}", action="pipeline.delete",
          target=pl.id, tenant_id=p.tenant_id)
    db.commit()
    hub.emit(p.tenant_id, "pipeline.changed", {"action": "delete", "name": name})
    return {"status": "archived", "message": f"Pipeline “{name}” deleted."}


# ───────────────────────────── Run engine ───────────────────────────────────
def run_dto(db, run: PipelineRun):
    steps = db.query(PipelineStepRun).filter_by(run_id=run.id).order_by(PipelineStepRun.seq).all()
    return {"id": run.id, "pipeline_id": run.pipeline_id, "status": run.status,
            "use_ai": run.use_ai, "final_report": run.final_report,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "ended_at": run.ended_at.isoformat() if run.ended_at else None,
            "steps": [{"id": s.id, "seq": s.seq, "agent_id": s.agent_id,
                       "agent_name": s.agent_name, "instruction": s.instruction,
                       "requires_approval": s.requires_approval, "status": s.status,
                       "output": s.output, "engine": s.engine} for s in steps]}


class RunIn(BaseModel):
    use_ai: bool = True


@router.post("/pipelines/{pid}/run")
def start_run(pid: str, body: RunIn, p: Principal = Depends(current_user),
              db: Session = Depends(get_db)):
    pl = db.get(Pipeline, pid)
    if not pl or pl.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Pipeline not found"})
    steps = db.query(PipelineStep).filter_by(pipeline_id=pid).order_by(PipelineStep.seq).all()
    if not steps:
        raise HTTPException(422, detail={"code": "VALIDATION_ERROR", "message": "Pipeline has no steps"})
    agents = {a.id: a for a in db.query(Agent).filter_by(tenant_id=p.tenant_id).all()}
    run = PipelineRun(id=ulid("ppr"), tenant_id=p.tenant_id, pipeline_id=pid,
                      status="running", use_ai=body.use_ai)
    db.add(run)
    db.flush()
    for s in steps:
        ag = agents.get(s.agent_id)
        db.add(PipelineStepRun(id=ulid("psr"), run_id=run.id, step_id=s.id, seq=s.seq,
                              agent_id=s.agent_id, agent_name=ag.name if ag else "Agent",
                              instruction=s.instruction, requires_approval=s.requires_approval,
                              status="pending"))
    audit(db, plane="local", actor=f"user:{p.user_id}", action="pipeline.run",
          target=run.id, tenant_id=p.tenant_id)
    db.commit()
    hub.emit(p.tenant_id, "pipeline.run_update", {"run_id": run.id, "status": "running"})
    return run_dto(db, run)


@router.get("/pipelines/runs/{run_id}")
def get_run(run_id: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    run = db.get(PipelineRun, run_id)
    if not run or run.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Run not found"})
    return run_dto(db, run)


def _execute_step(db, p, run, sr):
    """Run one step's agent via the local LLM (or fast fallback)."""
    ag = db.get(Agent, sr.agent_id)
    if ag:
        ag.status = "working"
        hub.emit(p.tenant_id, "agent.status", {"agent_id": ag.id, "status": "working", "name": ag.name})
    prior = db.query(PipelineStepRun).filter(
        PipelineStepRun.run_id == run.id, PipelineStepRun.seq < sr.seq,
        PipelineStepRun.status == "done").order_by(PipelineStepRun.seq).all()
    context = "\n\n".join(f"[{x.agent_name}] {x.output}" for x in prior if x.output)[:2500]

    output, engine = None, "template"
    if run.use_ai:
        system = (f"You are {sr.agent_name}, the {ag.designation if ag else 'specialist'} "
                  f"in an AI company. Do the assigned task and return only the work product, "
                  f"concise and usable (use short paragraphs or bullets).")
        prompt = (f"Previous team output:\n{context or '(none)'}\n\n"
                  f"Your task: {sr.instruction}")
        output = llm.chat(prompt, system=system, smart=False, num_predict=400, timeout=150)
        engine = "local-llm" if output else "template"
    if not output:
        output = (f"{sr.agent_name} completed: {sr.instruction} "
                  f"(based on {len(prior)} prior step(s)).")
    sr.output = output
    sr.engine = engine
    if ag:
        ag.status = "idle"
        hub.emit(p.tenant_id, "agent.status", {"agent_id": ag.id, "status": "idle", "name": ag.name})


def _finalize(db, p, run):
    done = db.query(PipelineStepRun).filter_by(run_id=run.id, status="done").order_by(
        PipelineStepRun.seq).all()
    combined = "\n\n".join(f"### {s.agent_name} — {s.instruction}\n{s.output}" for s in done)
    report = None
    if run.use_ai and combined:
        report = llm.chat(
            f"Team work:\n{combined[:3000]}\n\nWrite a short executive summary of what the "
            f"team produced and the recommended next steps.",
            system="You are the CEO Agent summarizing your team's work for the owner. "
                   "Be concise (5-8 lines).", smart=False, num_predict=300, timeout=150)
    if not report:
        report = ("Pipeline complete. " + " ".join(
            f"{s.agent_name} delivered their step." for s in done))
    run.final_report = report
    run.status = "completed"
    run.ended_at = now()
    # G3 Auto-Skill Capture from the completed crew run.
    pl = db.get(Pipeline, run.pipeline_id)
    from .skills import capture_skill
    capture_skill(db, p.tenant_id, pl.name if pl else "Pipeline",
                  [{"instruction": s.instruction, "agent_name": s.agent_name} for s in done],
                  run.id, agent_name="the crew")
    hub.emit(p.tenant_id, "pipeline.run_update", {"run_id": run.id, "status": "completed"})


@router.post("/pipelines/runs/{run_id}/advance")
def advance_run(run_id: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Execute the next pending step (one LLM call). Stops at approval gates."""
    run = db.get(PipelineRun, run_id)
    if not run or run.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Run not found"})
    if run.status in ("completed", "failed", "canceled"):
        return run_dto(db, run)
    # Blocked on an approval gate?
    awaiting = db.query(PipelineStepRun).filter_by(run_id=run_id, status="awaiting_approval").first()
    if awaiting:
        run.status = "waiting_approval"
        db.commit()
        return run_dto(db, run)

    nxt = db.query(PipelineStepRun).filter_by(run_id=run_id, status="pending").order_by(
        PipelineStepRun.seq).first()
    if not nxt:
        _finalize(db, p, run)
        db.commit()
        return run_dto(db, run)

    nxt.status = "running"
    hub.emit(p.tenant_id, "pipeline.step_update",
             {"run_id": run_id, "step_run_id": nxt.id, "seq": nxt.seq,
              "agent_name": nxt.agent_name, "status": "running"})
    db.commit()

    _execute_step(db, p, run, nxt)

    if nxt.requires_approval:
        nxt.status = "awaiting_approval"
        run.status = "waiting_approval"
    else:
        nxt.status = "done"
        run.status = "running"
    hub.emit(p.tenant_id, "pipeline.step_update",
             {"run_id": run_id, "step_run_id": nxt.id, "seq": nxt.seq,
              "agent_name": nxt.agent_name, "status": nxt.status})

    # If that was the last step and no approval needed, finalize now.
    db.flush()  # ensure the just-set status is visible to the count (autoflush is off)
    remaining = db.query(PipelineStepRun).filter(
        PipelineStepRun.run_id == run_id,
        PipelineStepRun.status.in_(["pending", "awaiting_approval"])).count()
    if remaining == 0:
        _finalize(db, p, run)
    db.commit()
    return run_dto(db, run)


class DecideStepIn(BaseModel):
    step_run_id: str
    decision: str            # approve | reject
    reason: str | None = None


@router.post("/pipelines/runs/{run_id}/decide")
def decide_step(run_id: str, body: DecideStepIn, p: Principal = Depends(current_user),
                db: Session = Depends(get_db)):
    run = db.get(PipelineRun, run_id)
    if not run or run.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Run not found"})
    sr = db.get(PipelineStepRun, body.step_run_id)
    if not sr or sr.run_id != run_id or sr.status != "awaiting_approval":
        raise HTTPException(409, detail={"code": "CONFLICT", "message": "Step not awaiting approval"})
    if body.decision == "approve":
        sr.status = "done"
        run.status = "running"
        audit(db, plane="local", actor=f"user:{p.user_id}", action="pipeline.step.approve",
              target=sr.id, tenant_id=p.tenant_id)
        db.flush()  # make sr='done' visible to the count (autoflush is off)
        remaining = db.query(PipelineStepRun).filter(
            PipelineStepRun.run_id == run_id,
            PipelineStepRun.status.in_(["pending", "awaiting_approval"])).count()
        if remaining == 0:
            _finalize(db, p, run)
    else:
        sr.status = "rejected"
        run.status = "failed"
        run.ended_at = now()
        audit(db, plane="local", actor=f"user:{p.user_id}", action="pipeline.step.reject",
              target=sr.id, tenant_id=p.tenant_id)
    hub.emit(p.tenant_id, "pipeline.step_update",
             {"run_id": run_id, "step_run_id": sr.id, "seq": sr.seq,
              "agent_name": sr.agent_name, "status": sr.status})
    db.commit()
    return run_dto(db, run)


@router.get("/pipelines/{pid}/runs")
def list_runs(pid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(PipelineRun).filter_by(pipeline_id=pid).order_by(
        PipelineRun.started_at.desc()).all()
    return [{"id": r.id, "status": r.status,
             "started_at": r.started_at.isoformat() if r.started_at else None,
             "final_report": r.final_report} for r in rows]


# ──────────────────────── voice / natural-language control ───────────────────
from pydantic import BaseModel as _BM


class PipelineVoiceIn(_BM):
    transcript: str


def _match_pipeline(db, tenant_id, text):
    low = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    toks = [t for t in low.split() if len(t) >= 3]
    best, score = None, 0
    for pl in db.query(Pipeline).filter(Pipeline.tenant_id == tenant_id,
                                        Pipeline.status != "archived").all():
        nm = (pl.name or "").lower()
        if nm and nm in low:
            return pl
        for w in re.findall(r"[a-z]+", nm):
            if len(w) > 3 and w not in ("pipeline", "the", "and", "for") and w in toks and len(w) > score:
                best, score = pl, len(w)
    return best


@router.post("/pipelines/resolve")
def pipelines_resolve(body: PipelineVoiceIn, p: Principal = Depends(current_user),
                      db: Session = Depends(get_db)):
    """Turn a spoken/typed phrase into a concrete Pipelines action."""
    text = (body.transcript or "").strip()
    low = text.lower()
    if not text:
        return {"action": "none", "message": "I didn't catch that."}

    # build a new pipeline
    if re.search(r"\b(build|create|new|make|set ?up)\b", low) and "pipeline" in low \
            and not _match_pipeline(db, p.tenant_id, text):
        return {"action": "build", "message": "Opening the pipeline builder."}

    pl = _match_pipeline(db, p.tenant_id, text)
    if pl:
        if re.search(r"\b(run|start|execute|kick off|go|launch)\b", low):
            return {"action": "run", "id": pl.id, "name": pl.name, "message": f"Running “{pl.name}”."}
        if re.search(r"\b(delete|remove|archive|get rid of)\b", low):
            return {"action": "delete", "id": pl.id, "name": pl.name, "message": f"Deleting “{pl.name}”."}
        if re.search(r"\b(edit|change|modify|update)\b", low):
            return {"action": "edit", "id": pl.id, "name": pl.name, "message": f"Editing “{pl.name}”."}
        if re.search(r"\b(duplicate|clone|copy)\b", low):
            return {"action": "duplicate", "id": pl.id, "name": pl.name, "message": f"Duplicating “{pl.name}”."}
        if re.search(r"\b(open|show|view|see|details?)\b", low):
            return {"action": "edit", "id": pl.id, "name": pl.name, "message": f"Opening “{pl.name}”."}

    if re.search(r"\b(build|create|new)\b", low):
        return {"action": "build", "message": "Opening the pipeline builder."}
    return {"action": "none",
            "message": "Try \"build a pipeline\", \"run the onboarding pipeline\", or \"delete the launch pipeline\"."}
